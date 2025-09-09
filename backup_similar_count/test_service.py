"""
خدمة إدارة الاختبارات
"""
from typing import Dict, List, Optional, Tuple
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from core.models import Student, TestSession, TestQuestion, Juz, Quarter, Page, Ayah, SimilarityGroup, Phrase, PhraseOccurrence


class TestService:
    """خدمة إدارة الاختبارات"""
    
    def __init__(self, student: Student):
        self.student = student
    
    def create_test_session(
        self,
        test_type: str,
        selected_juz: List[int],
        selected_quarters: List[int],
        num_questions: int,
        difficulty: str = 'mixed',
        position_order: str = 'normal'
    ) -> TestSession:
        """إنشاء جلسة اختبار جديدة"""
        
        with transaction.atomic():
            # إنشاء جلسة الاختبار
            session = TestSession.objects.create(
                student=self.student,
                test_type=test_type,
                num_questions=num_questions,
                difficulty=difficulty,
                position_order=position_order,
                started_at=timezone.now()
            )
            
            # إضافة الأجزاء المختارة
            if selected_juz:
                session.juzs.set(Juz.objects.filter(number__in=selected_juz))
            
            # إضافة الأرباع المختارة
            if selected_quarters:
                session.quarters.set(Quarter.objects.filter(id__in=selected_quarters))
            
            # إنشاء الأسئلة
            questions = self._generate_questions(session, test_type, num_questions, difficulty)
            session.questions.set(questions)
            
            return session
    
    def _generate_questions(
        self,
        session: TestSession,
        test_type: str,
        num_questions: int,
        difficulty: str
    ) -> List[TestQuestion]:
        """إنشاء أسئلة الاختبار"""
        
        questions = []
        
        if test_type == 'similar_count':
            questions = self._generate_similar_count_questions(session, num_questions, difficulty)
        elif test_type == 'similar_on_pages':
            questions = self._generate_similar_on_pages_questions(session, num_questions, difficulty)
        elif test_type == 'verse_location_quarters':
            questions = self._generate_verse_location_questions(session, num_questions, difficulty)
        
        return questions
    
    def _generate_similar_count_questions(
        self,
        session: TestSession,
        num_questions: int,
        difficulty: str
    ) -> List[TestQuestion]:
        """إنشاء أسئلة عدد المواضع المتشابهة"""
        
        # الحصول على العبارات المتاحة
        phrases = self._get_available_phrases(session, difficulty)
        
        questions = []
        for i in range(min(num_questions, len(phrases))):
            phrase = phrases[i]
            
            # إنشاء السؤال
            question = TestQuestion.objects.create(
                session=session,
                question_type='similar_count',
                phrase=phrase,
                question_text=f"كم موضع تظهر فيه العبارة: \"{phrase.text}\"؟",
                correct_answer=str(phrase.occurrences.count())
            )
            
            questions.append(question)
        
        return questions
    
    def _generate_similar_on_pages_questions(
        self,
        session: TestSession,
        num_questions: int,
        difficulty: str
    ) -> List[TestQuestion]:
        """إنشاء أسئلة المواضع المتشابهة على الصفحات"""
        
        # الحصول على العبارات المتاحة
        phrases = self._get_available_phrases(session, difficulty)
        
        questions = []
        for i in range(min(num_questions, len(phrases))):
            phrase = phrases[i]
            
            # إنشاء السؤال
            first_occurrence = phrase.occurrences.first()
            page_number = first_occurrence.ayah.page.number if first_occurrence and first_occurrence.ayah.page else 0
            question = TestQuestion.objects.create(
                session=session,
                question_type='similar_on_pages',
                phrase=phrase,
                question_text=f"في أي صفحة تظهر العبارة: \"{phrase.text}\"؟",
                correct_answer=str(page_number)
            )
            
            questions.append(question)
        
        return questions
    
    def _generate_verse_location_questions(
        self,
        session: TestSession,
        num_questions: int,
        difficulty: str
    ) -> List[TestQuestion]:
        """إنشاء أسئلة موقع الآيات في الأرباع"""
        
        # الحصول على الآيات المتاحة
        ayahs = self._get_available_ayahs(session, difficulty)
        
        questions = []
        for i in range(min(num_questions, len(ayahs))):
            ayah = ayahs[i]
            
            # إنشاء السؤال
            question = TestQuestion.objects.create(
                session=session,
                question_type='verse_location_quarters',
                question_text=f"في أي ربع توجد الآية: \"{ayah.text[:50]}...\"؟",
                correct_answer=str(ayah.quarter.id)
            )
            
            questions.append(question)
        
        return questions
    
    def _get_available_phrases(self, session: TestSession, difficulty: str) -> List[Phrase]:
        """الحصول على العبارات المتاحة للاختبار"""
        
        # فلترة العبارات حسب الأجزاء والأرباع المختارة
        phrases = Phrase.objects.all()
        
        if session.juzs.exists():
            juz_numbers = session.juzs.values_list('number', flat=True)
            phrases = phrases.filter(occurrences__ayah__quarter__juz__number__in=juz_numbers)
        
        if session.quarters.exists():
            quarter_ids = session.quarters.values_list('id', flat=True)
            phrases = phrases.filter(occurrences__ayah__quarter__id__in=quarter_ids)
        
        # تطبيق مستوى الصعوبة
        if difficulty == 'easy':
            phrases = phrases.annotate(occurrence_count=Count('occurrences')).filter(occurrence_count__lte=3)
        elif difficulty == 'medium':
            phrases = phrases.annotate(occurrence_count=Count('occurrences')).filter(occurrence_count__lte=5)
        elif difficulty == 'hard':
            phrases = phrases.annotate(occurrence_count=Count('occurrences')).filter(occurrence_count__gt=5)
        
        return list(phrases.distinct())
    
    def _get_available_ayahs(self, session: TestSession, difficulty: str) -> List[Ayah]:
        """الحصول على الآيات المتاحة للاختبار"""
        
        # فلترة الآيات حسب الأجزاء والأرباع المختارة
        ayahs = Ayah.objects.all()
        
        if session.juzs.exists():
            juz_numbers = session.juzs.values_list('number', flat=True)
            ayahs = ayahs.filter(quarter__juz__number__in=juz_numbers)
        
        if session.quarters.exists():
            quarter_ids = session.quarters.values_list('id', flat=True)
            ayahs = ayahs.filter(quarter__id__in=quarter_ids)
        
        return list(ayahs.distinct())
    
    def submit_answer(self, question_id: int, answer: str) -> Tuple[bool, str]:
        """تقديم إجابة على سؤال"""
        
        try:
            question = TestQuestion.objects.get(id=question_id, session__student=self.student)
            
            # حفظ الإجابة
            question.user_answer = answer
            question.is_correct = str(question.correct_answer) == str(answer)
            question.answered_at = timezone.now()
            question.save()
            
            return question.is_correct, "تم حفظ الإجابة بنجاح"
            
        except TestQuestion.DoesNotExist:
            return False, "السؤال غير موجود"
    
    def complete_test_session(self, session_id: int) -> Dict:
        """إكمال جلسة الاختبار وحساب النتائج"""
        
        try:
            session = TestSession.objects.get(id=session_id, student=self.student)
            
            # حساب النتائج
            total_questions = session.questions.count()
            correct_answers = session.questions.filter(is_correct=True).count()
            wrong_answers = session.questions.filter(is_correct=False).count()
            unanswered = session.questions.filter(user_answer__isnull=True).count()
            
            # حفظ النتائج
            session.completed_at = timezone.now()
            session.total_questions = total_questions
            session.correct_answers = correct_answers
            session.wrong_answers = wrong_answers
            session.unanswered = unanswered
            session.save()
            
            return {
                'total': total_questions,
                'correct': correct_answers,
                'wrong': wrong_answers,
                'unanswered': unanswered,
                'score': correct_answers,
                'accuracy': (correct_answers / total_questions * 100) if total_questions > 0 else 0
            }
            
        except TestSession.DoesNotExist:
            return {'error': 'جلسة الاختبار غير موجودة'}

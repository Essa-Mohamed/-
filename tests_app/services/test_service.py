"""خدمة إدارة الاختبارات"""
from typing import Dict, List
from django.db import transaction
from django.utils import timezone

from core.models import Student, TestSession, Juz, Quarter
from .question_generator_factory import QuestionGeneratorFactory


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
            
            return session
    
    def generate_questions_for_session(
        self,
        session: TestSession,
        num_questions: int,
        difficulty: str,
    ) -> List[Dict]:
        """إنشاء أسئلة الاختبار باستخدام أنماط التوليد المختلفة"""

        generator = QuestionGeneratorFactory.get_generator(session.test_type)
        return generator.generate(session, num_questions, difficulty)
    
    def generate_verse_location_questions(
        self,
        session: TestSession,
        num_questions: int,
        difficulty: str,
    ) -> List[Dict]:
        """واجهة متوافقة لتوليد أسئلة موقع الآيات"""

        generator = QuestionGeneratorFactory.get_generator('verse_location_quarters')
        return generator.generate(session, num_questions, difficulty)
    
    def make_options(self, correct_count: int) -> List[int]:
        """اختيارات مرتّبة تصاعديًا بدون تدوير، حول الإجابة الصحيحة."""
        pool = {correct_count}
        for off in (-3, -2, -1, 1, 2, 3, 4, 5):
            v = correct_count + off
            if v >= 1:
                pool.add(v)
            if len(pool) >= 4:
                break
        return sorted(pool)[:4]
    
    def build_scope_label(self, selected_juz_ids: List[int], selected_quarter_ids: List[int]) -> str:
        """بناء تسمية النطاق المختار"""
        if selected_quarter_ids:
            quarters = Quarter.objects.filter(id__in=selected_quarter_ids).select_related('juz')
            by_juz = {}
            for q in quarters:
                by_juz.setdefault(q.juz.number, []).append(q)
            parts = []
            for j in sorted(by_juz):
                qs = by_juz[j]
                if len(qs) == 8:
                    parts.append(f"الجزء {j}")
                else:
                    idx = ', '.join(f"الربع {q.index_in_juz}" for q in sorted(qs, key=lambda x: x.index_in_juz))
                    parts.append(f"الجزء {j} - {idx}")
            return "اختبار على: " + "؛ ".join(parts)
        elif selected_juz_ids:
            lbl = '؛ '.join(f"الجزء {j}" for j in sorted(selected_juz_ids))
            return f"اختبار على: {lbl}"
        return "اختبار على: نطاق غير محدد"

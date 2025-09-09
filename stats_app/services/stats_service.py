"""
خدمة الإحصائيات والليدر بورد
"""
from typing import Dict, List, Optional
from django.db.models import Count, Sum, Avg, Q
from django.contrib.auth.models import User

from core.models import Student, TestSession, TestQuestion


class StatsService:
    """خدمة الإحصائيات والليدر بورد"""
    
    def __init__(self, student: Optional[Student] = None):
        self.student = student
    
    def get_student_stats(self, student: Student) -> Dict:
        """الحصول على إحصائيات الطالب"""
        
        # إحصائيات الاختبارات المكتملة
        sessions = TestSession.objects.filter(student=student, completed=True)
        
        total_sessions = sessions.count()
        
        # حساب الإحصائيات من الأسئلة
        total_questions = 0
        correct_answers = 0
        wrong_answers = 0
        unanswered_questions = 0
        
        for session in sessions:
            questions = session.questions.all()
            total_questions += questions.count()
            correct_answers += questions.filter(is_correct=True).count()
            
            # الإجابات الخاطئة: الأسئلة التي أُجيب عليها لكن الإجابة خاطئة
            wrong_answers += questions.filter(
                is_correct=False,
                student_response__isnull=False
            ).exclude(student_response='').count()
            
            # الإجابات غير المجابة: الأسئلة التي لم يُجب عليها إطلاقاً
            unanswered_questions += questions.filter(
                student_response__isnull=True
            ).count() + questions.filter(
                student_response=''
            ).count()
        
        # حساب الدقة بناءً على الأسئلة التي أُجيب عليها فعلاً
        answered_questions = correct_answers + wrong_answers
        accuracy = (correct_answers / answered_questions * 100) if answered_questions > 0 else 0
        
        # إحصائيات حسب نوع الاختبار
        test_type_stats = {}
        for test_type in ['similar_count', 'similar_on_pages', 'verse_location_quarters']:
            type_sessions = sessions.filter(test_type=test_type)
            if type_sessions.exists():
                type_questions = 0
                type_correct = 0
                type_wrong = 0
                type_unanswered = 0
                
                for session in type_sessions:
                    questions = session.questions.all()
                    type_questions += questions.count()
                    type_correct += questions.filter(is_correct=True).count()
                    type_wrong += questions.filter(
                        is_correct=False,
                        student_response__isnull=False
                    ).exclude(student_response='').count()
                    type_unanswered += questions.filter(
                        student_response__isnull=True
                    ).count() + questions.filter(
                        student_response=''
                    ).count()
                
                type_answered = type_correct + type_wrong
                test_type_stats[test_type] = {
                    'sessions': type_sessions.count(),
                    'questions': type_questions,
                    'correct': type_correct,
                    'wrong': type_wrong,
                    'unanswered': type_unanswered,
                    'accuracy': (type_correct / type_answered * 100) if type_answered > 0 else 0
                }
        
        return {
            'total_sessions': total_sessions,
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'wrong_answers': wrong_answers,
            'unanswered': unanswered_questions,
            'accuracy': accuracy,
            'test_type_stats': test_type_stats
        }
    
    def get_leaderboard(self, limit: int = 50) -> List[Dict]:
        """الحصول على لوحة المنافسة"""
        
        # الحصول على جميع الطلاب مع إحصائياتهم
        students = Student.objects.all()
        leaderboard = []
        
        for student in students:
            stats = self.get_student_stats(student)
            
            if stats['total_questions'] > 0:  # فقط الطلاب الذين لديهم اختبارات
                # حساب النقاط (الدقة 80% + الإجابات الصحيحة + عدد الامتحانات)
                score = (stats['accuracy'] * 0.8) + stats['correct_answers'] + stats['total_sessions']
                
                leaderboard.append({
                    'student_id': student.id,
                    'display_name': student.display_name,
                    'avatar': student.avatar.url if student.avatar else None,
                    'score': round(score, 1),
                    'exams': stats['total_sessions'],
                    'correct': stats['correct_answers'],
                    'wrong': stats['wrong_answers'],
                    'unanswered': stats['unanswered'],
                    'accuracy_pct': round(stats['accuracy'], 1)
                })
        
        # ترتيب حسب الدقة أولاً، ثم الإجابات الصحيحة
        leaderboard.sort(key=lambda x: (x['accuracy_pct'], x['correct']), reverse=True)
        
        # إضافة الترتيب
        for i, student in enumerate(leaderboard, 1):
            student['rank'] = i
        
        return leaderboard[:limit]
    
    def get_student_rank(self, student: Student) -> Optional[int]:
        """الحصول على ترتيب الطالب في اللوحة"""
        
        leaderboard = self.get_leaderboard()
        
        for student_data in leaderboard:
            if student_data['student_id'] == student.id:
                return student_data['rank']
        
        return None
    
    def reset_student_stats(self, student: Student) -> bool:
        """إعادة تعيين إحصائيات الطالب"""
        
        try:
            # حذف جميع جلسات الاختبار المكتملة
            TestSession.objects.filter(student=student, completed=True).delete()
            
            return True
            
        except Exception as e:
            print(f"خطأ في إعادة تعيين الإحصائيات: {e}")
            return False
    
    def get_recent_activity(self, student: Student, limit: int = 10) -> List[Dict]:
        """الحصول على النشاط الأخير للطالب"""
        
        sessions = TestSession.objects.filter(
            student=student,
            completed=True
        ).order_by('-created_at')[:limit]
        
        activity = []
        for session in sessions:
            questions = session.questions.all()
            total_questions = questions.count()
            correct_answers = questions.filter(is_correct=True).count()
            
            activity.append({
                'id': session.id,
                'test_type': session.get_test_type_display(),
                'completed_at': session.created_at,  # استخدام created_at بدلاً من completed_at
                'total_questions': total_questions,
                'correct_answers': correct_answers,
                'accuracy': (correct_answers / total_questions * 100) if total_questions > 0 else 0
            })
        
        return activity
    
    def get_global_stats(self) -> Dict:
        """الحصول على الإحصائيات العامة للمنصة"""
        
        total_students = Student.objects.count()
        total_sessions = TestSession.objects.filter(completed=True).count()
        
        # حساب إجمالي الأسئلة من جميع الجلسات المكتملة
        total_questions = 0
        total_correct = 0
        
        for session in TestSession.objects.filter(completed=True):
            questions = session.questions.all()
            total_questions += questions.count()
            total_correct += questions.filter(is_correct=True).count()
        
        # متوسط الدقة
        avg_accuracy = (total_correct / total_questions * 100) if total_questions > 0 else 0
        
        return {
            'total_students': total_students,
            'total_sessions': total_sessions,
            'total_questions': total_questions,
            'average_accuracy': round(avg_accuracy, 1)
        }

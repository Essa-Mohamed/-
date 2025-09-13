from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from students.models import Student
from testing.models import TestSession, TestQuestion


def _score_formula(exams, correct, wrong, unanswered):
    """حساب النقاط بناءً على الإحصائيات"""
    base = correct - 0.6 * wrong - 0.2 * unanswered
    return max(0, int(base + exams * 2))


def _user_stats(student: Student):
    """حساب إحصائيات الطالب"""
    # نعتمد فقط على الجلسات المكتملة ونستبعد الأسئلة غير المُجابة من الصحيح/الخطأ
    exams = TestSession.objects.filter(student=student, completed=True).count()
    correct = TestQuestion.objects.filter(session__student=student, session__completed=True, is_correct=True).count()
    wrong = TestQuestion.objects.filter(session__student=student, session__completed=True, is_correct=False).count()
    unanswered = TestQuestion.objects.filter(session__student=student, session__completed=True, student_response__isnull=True).count() + TestQuestion.objects.filter(session__student=student, session__completed=True, student_response='').count()

    return {'exams': exams, 'correct': correct, 'wrong': wrong, 'unanswered': unanswered}


def _leaderboard():
    """حساب لوحة المنافسة"""
    # الحصول على جميع الطلاب الذين لديهم جلسات مكتملة
    students_with_sessions = Student.objects.filter(
        testsession__completed=True
    ).distinct()
    
    leaderboard_data = []
    
    for student in students_with_sessions:
        stats = _user_stats(student)
        score = _score_formula(stats['exams'], stats['correct'], stats['wrong'], stats['unanswered'])
        
        if stats['exams'] > 0:  # فقط الطلاب الذين لديهم امتحانات مكتملة
            leaderboard_data.append({
                'student_id': student.id,
                'display_name': student.display_name,
                'avatar': student.avatar.url if student.avatar else None,
                'skin': student.skin,
                'score': score,
                'exams': stats['exams'],
                'correct': stats['correct'],
                'wrong': stats['wrong'],
                'unanswered': stats['unanswered'],
                'accuracy_pct': (stats['correct'] / (stats['correct'] + stats['wrong'])) * 100 if (stats['correct'] + stats['wrong']) > 0 else None
            })
    
    # ترتيب حسب النقاط (تنازلي) ثم عدد الامتحانات (تنازلي)
    leaderboard_data.sort(key=lambda x: (x['score'], x['exams']), reverse=True)
    
    # إضافة الترتيب
    for i, student_data in enumerate(leaderboard_data):
        student_data['rank'] = i + 1
    
    return leaderboard_data


@login_required
def stats(request):
    """صفحة إحصائيات الطالب"""
    student = get_object_or_404(Student, user=request.user)
    data = _user_stats(student)
    
    # إضافة إجمالي الأسئلة
    data['total_questions'] = data['correct'] + data['wrong'] + data['unanswered']
    
    # إضافة معدل الدقة
    if data['correct'] + data['wrong'] > 0:
        data['accuracy'] = (data['correct'] / (data['correct'] + data['wrong'])) * 100
    else:
        data['accuracy'] = 0
    
    # إضافة آخر الامتحانات
    completed_sessions = TestSession.objects.filter(
        student=student,
        completed=True
    ).order_by('-completed_at')
    
    # تشخيص: طباعة عدد الجلسات المكتملة
    print(f"DEBUG: عدد الجلسات المكتملة للطالب {student.id}: {completed_sessions.count()}")
    for session in completed_sessions:
        print(f"DEBUG: جلسة {session.id} - مكتملة: {session.completed} - وقت الانتهاء: {session.completed_at}")
    
    # تشخيص: فحص جميع جلسات الطالب
    all_sessions = TestSession.objects.filter(student=student)
    print(f"DEBUG: إجمالي جلسات الطالب: {all_sessions.count()}")
    for session in all_sessions:
        print(f"DEBUG: جلسة {session.id} - مكتملة: {session.completed} - نوع: {session.test_type} - وقت الإنشاء: {session.created_at} - وقت الانتهاء: {session.completed_at}")
    
    recent_sessions = []
    for session in completed_sessions[:5]:
        questions = session.questions.all()
        total_questions = questions.count()
        correct_answers = questions.filter(is_correct=True).count()
        
        if total_questions > 0:
            score_percentage = (correct_answers / total_questions) * 100
        else:
            score_percentage = 0
        
        recent_sessions.append({
            'id': session.id,
            'test_type': session.test_type,
            'score': score_percentage,
            'created_at': session.completed_at or session.created_at,
            'total_questions': total_questions,
            'correct_answers': correct_answers
        })
    
    return render(request, 'stats/stats.html', {
        'student': student,
        'stats': data,
        'recent_sessions': recent_sessions,
        'hide_footer': False
    })


@login_required
def reset_stats(request):
    """إعادة تعيين إحصائيات الطالب من الصفر"""
    if request.method == 'POST':
        student = get_object_or_404(Student, user=request.user)
        
        try:
            # حذف جميع جلسات الاختبار المكتملة
            TestSession.objects.filter(student=student, completed=True).delete()
            
            # حذف جميع الأسئلة
            TestQuestion.objects.filter(session__student=student).delete()
            
            # حذف جميع جلسات الاختبار غير المكتملة
            TestSession.objects.filter(student=student, completed=False).delete()
            
            messages.success(request, "تم إعادة تعيين إحصائياتك بنجاح! يمكنك الآن البدء من جديد.")
            return redirect('stats_app:stats')
            
        except Exception as e:
            messages.error(request, f"حدث خطأ أثناء إعادة تعيين الإحصائيات: {e}")
            return redirect('stats_app:stats')
    
    # إذا لم يكن POST، نعيد توجيه المستخدم
    return redirect('stats_app:stats')


@login_required
def leaderboard(request):
    """لوحة المنافسة"""
    student = get_object_or_404(Student, user=request.user)
    rows = _leaderboard()
    my_rank = next((r['rank'] for r in rows if r['student_id'] == student.id), None)
    return render(request, 'stats/leaderboard.html', {
        'rows': rows,
        'student': student,
        'my_rank': my_rank,
        'hide_footer': False
    })


def student_profile(request, student_id):
    """عرض بروفايل الطالب مع إحصائياته"""
    student = get_object_or_404(Student, id=student_id)
    
    # استخدام نفس الدالة المستخدمة في لوحة المنافسة
    stats = _user_stats(student)
    score = _score_formula(stats['exams'], stats['correct'], stats['wrong'], stats['unanswered'])
    
    # حساب الدقة
    accuracy_pct = None
    if (stats['correct'] + stats['wrong']) > 0:
        accuracy_pct = (stats['correct'] / (stats['correct'] + stats['wrong'])) * 100
    
    # الحصول على جلسات الاختبار المكتملة
    completed_sessions = TestSession.objects.filter(
        student=student,
        completed=True
    ).order_by('-completed_at')
    
    # الحصول على آخر 5 جلسات مع إضافة البيانات المطلوبة
    recent_sessions = []
    for session in completed_sessions[:5]:
        # حساب النقاط للجلسة
        questions = session.questions.all()
        total_questions = questions.count()
        correct_answers = questions.filter(is_correct=True).count()
        wrong_answers = questions.filter(is_correct=False).count()
        
        # حساب النسبة المئوية
        if total_questions > 0:
            score_percentage = (correct_answers / total_questions) * 100
        else:
            score_percentage = 0
        
        recent_sessions.append({
            'id': session.id,
            'test_type': session.test_type,
            'score': score_percentage,
            'created_at': session.completed_at or session.created_at,
            'total_questions': total_questions,
            'correct_answers': correct_answers,
            'wrong_answers': wrong_answers
        })
    
    context = {
        'profile_student': student,
        'total_questions': stats['correct'] + stats['wrong'] + stats['unanswered'],
        'answered_questions': stats['correct'] + stats['wrong'],
        'correct_questions': stats['correct'],
        'wrong_questions': stats['wrong'],
        'unanswered_questions': stats['unanswered'],
        'accuracy_pct': accuracy_pct,
        'score': score,
        'completed_sessions': stats['exams'],
        'recent_sessions': recent_sessions,
        'hide_footer': False
    }
    
    return render(request, 'stats/student_profile.html', context)


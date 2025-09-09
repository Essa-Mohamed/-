from django.shortcuts import redirect
from django.urls import reverse
from core import views as core_views


def _ensure_type_in_session(request):
    # نثبت نوع الاختبار في السيشن لضمان سلوك المنطق الحالي
    request.session['selected_test_type'] = 'similar_count'


def selection(request):
    _ensure_type_in_session(request)
    return core_views.test_selection(request)


def start(request):
    _ensure_type_in_session(request)
    return core_views.start_test(request)


def question(request):
    _ensure_type_in_session(request)
    return core_views.test_question(request)


def result(request):
    from django.shortcuts import render, get_object_or_404
    from core.models import Student
    
    _ensure_type_in_session(request)
    
    # جلب بيانات النتائج من السيشن
    results_data = request.session.get('test_results')
    if not results_data:
        # لو مفيش نتائج، نعيد للاختيار
        return redirect('tests:similar_count:selection')
    
    # جلب بيانات الطالب
    student = get_object_or_404(Student, id=results_data['student_id'])
    
    # مسح بيانات النتائج من السيشن بعد العرض
    request.session.pop('test_results', None)
    
    return render(request, 'core/test_result.html', {
        'student': student,
        'score': results_data['score'],
        'total': results_data['total'],
        'detailed_results': results_data['detailed_results'],
        'scope_label': results_data['scope_label'],
        'wrong': results_data['wrong'],
        'test_type': results_data['test_type'],
        'hide_footer': True
    })


def report(request):
    # إعادة استخدام شاشة الإبلاغ الحالية
    return core_views.report_question(request)



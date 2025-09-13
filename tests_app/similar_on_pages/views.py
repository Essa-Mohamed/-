from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from students.models import Student
from quran_structure.models import Juz, Quarter, Ayah
from testing.models import TestSession, TestQuestion
from core.models import Phrase, PhraseOccurrence
from core.services.user_service import UserService
from tests_app.services.test_service import TestService


def _ensure_type_in_session(request):
    # نثبت نوع الاختبار في السيشن لضمان سلوك المنطق الحالي
    request.session['selected_test_type'] = 'similar_on_pages'


@login_required
def selection(request):
    """صفحة اختيار النطاق للاختبار"""
    _ensure_type_in_session(request)
    
    # الحصول على الطالب
    user_service = UserService()
    student = user_service.get_or_create_student(request.user)
    
    if request.method == 'POST':
        sel_juz = request.POST.getlist('selected_juz')
        sel_q = request.POST.getlist('selected_quarters')
        try:
            num_q = int(request.POST.get('num_questions', 5))
        except ValueError:
            num_q = 5
        if num_q not in [5, 10, 15, 20]:
            num_q = 5
        
        difficulty = request.POST.get('difficulty', 'mixed')
        
        sel_juz = [int(j) for j in sel_juz if str(j).isdigit()]
        sel_q = [int(q) for q in sel_q if str(q).isdigit()]
        if not sel_juz and not sel_q:
            messages.error(request, "لازم تختار جزء أو رُبع.")
            return redirect('tests:similar_on_pages:selection')
        
        request.session.update({
            'selected_juz': sel_juz,
            'selected_quarters': sel_q,
            'num_questions': num_q,
            'difficulty': difficulty,
            'test_index': 0,
            'score': 0,
        })
        request.session.pop('scope_label', None)
        return redirect('tests:similar_on_pages:start')
    
    # تجهيز عرض الأجزاء + أرباعها
    juz_list = Juz.objects.all().order_by('number')
    juz_quarters_map = {}
    for j in juz_list:
        qs = list(Quarter.objects.filter(juz=j).order_by('index_in_juz'))
        first_label = qs[0].label if qs else ''
        juz_quarters_map[j] = {'quarters': qs, 'first_label': first_label}
    
    return render(request, 'core/test_selection.html', {
        'student': student,
        'juz_quarters_map': juz_quarters_map,
        'num_questions_options': [5, 10, 15, 20],
        'show_splash': True,
        'hide_footer': False,
        'selected_test_type': request.session.get('selected_test_type', 'similar_on_pages'),
    })


@login_required
def start(request):
    """بدء الاختبار وإنشاء الأسئلة"""
    _ensure_type_in_session(request)
    
    # الحصول على الطالب
    user_service = UserService()
    student = user_service.get_or_create_student(request.user)
    
    juz_ids = request.session.get('selected_juz', [])
    q_ids = request.session.get('selected_quarters', [])
    desired = int(request.session.get('num_questions', 5))
    difficulty = request.session.get('difficulty', 'mixed')
    
    # إنشاء جلسة الاختبار
    test_service = TestService(student)
    session = test_service.create_test_session(
        test_type='similar_on_pages',
        selected_juz=juz_ids,
        selected_quarters=q_ids,
        num_questions=desired,
        difficulty=difficulty
    )
    
    # إنشاء الأسئلة
    questions = test_service.generate_questions_for_session(session, desired, difficulty)
    
    if not questions:
        messages.error(request, "مافيش عبارات متشابهة كافية فى النطاق.")
        return redirect('tests:similar_on_pages:selection')
    
    # حفظ الأسئلة في الجلسة
    request.session['questions'] = questions
    request.session['test_index'] = 0
    request.session['score'] = 0
    request.session['db_session_id'] = session.id
    request.session['scope_label'] = test_service.build_scope_label(juz_ids, q_ids)
    
    # إنشاء أسئلة في قاعدة البيانات للتتبع
    db_qids = []
    for _ in questions:
        tq = TestQuestion.objects.create(session=session)
        db_qids.append(tq.id)
    request.session['db_question_ids'] = db_qids
    
    return redirect('tests:similar_on_pages:question')


@login_required
def question(request):
    """صفحة سؤال الاختبار"""
    _ensure_type_in_session(request)
    
    # الحصول على الطالب
    user_service = UserService()
    student = user_service.get_or_create_student(request.user)
    
    idx = request.session.get('test_index', 0)
    qs = request.session.get('questions', [])
    total = len(qs)
    
    # انتهى الامتحان؟
    if idx >= total:
        score = request.session.get('score', 0)
        scope_lbl = request.session.get('scope_label', '')
        detailed = [{
            'phrase': q.get('phrase_text') or q.get('phrase', ''),
            'correct_count': q.get('correct_count'),
            'given_answer': q.get('given_answer'),
            'occurrences': q.get('literal_ayahs', []),
        } for q in qs]
        wrong = max(0, total - score)
        
        # علّم الجلسة كمكتملة
        db_sid = request.session.get('db_session_id')
        if db_sid:
            from django.utils import timezone
            TestSession.objects.filter(id=db_sid).update(
                completed=True,
                completed_at=timezone.now()
            )
        
        # نظّف السيشن
        for k in ['questions', 'test_index', 'score', 'selected_juz', 'selected_quarters',
                  'num_questions', 'scope_label', 'difficulty', 'db_session_id', 'db_question_ids']:
            request.session.pop(k, None)
    
    return render(request, 'core/test_result.html', {
            'student': student, 'score': score, 'total': total,
            'detailed_results': detailed,
            'scope_label': scope_lbl,
            'wrong': wrong,
            'hide_footer': True,
        })
    
    question = qs[idx]
    progress = round((idx + 1) / total * 100) if total else 0
    
    # إنهاء مبكر
    if request.method == 'POST' and request.POST.get('action') == 'end':
        db_sid = request.session.get('db_session_id')
        if db_sid:
            from django.utils import timezone
            TestSession.objects.filter(id=db_sid).update(
                completed=True,
                completed_at=timezone.now()
            )
        request.session['test_index'] = len(qs)
        return redirect('tests:similar_on_pages:question')
    
    if request.method == 'POST':
        ans = request.POST.get('occurrence')
        # خزّن الإجابة في السيشن
        try:
            qs[idx]['given_answer'] = int(ans)
        except (ValueError, TypeError):
            qs[idx]['given_answer'] = None
        request.session['questions'] = qs
        
        # الصحيحة لهذا السؤال
        try:
            correct_count = int(question.get('correct_count'))
        except (TypeError, ValueError):
            correct_count = -1
        
        # سجّل الإجابة في الـDB حسب ترتيب السؤال
        db_qids = request.session.get('db_question_ids') or []
        if isinstance(db_qids, list) and idx < len(db_qids):
            given = qs[idx]['given_answer']
            is_corr = bool(given is not None and int(given) == correct_count)
            TestQuestion.objects.filter(id=db_qids[idx]).update(
                student_response=str(given if given is not None else ''),
                is_correct=is_corr
            )
        
        # لو النوع صفحات → جهّز فلو الصفحات لهذا السؤال ولا تزود المؤشر
        selected_type = request.session.get('selected_test_type', 'similar_count')
        ans_val = None
        try:
            ans_val = int(ans) if ans and ans.isdigit() else None
        except Exception:
            ans_val = None
        
        if selected_type == 'similar_on_pages':
            request.session['pages_flow'] = {
                'q_index': idx,                           # نفس السؤال الحالي
                'target_total': max(0, ans_val or 0),     # عدد المواضع التي سيحددها
                'current': 1,                              # ابدأ بالموضع الأول
            }
            # استدعاء دالة تعيين العدد من core.views
            from core.views import _flow_set_total
            _flow_set_total(request, ans_val or 0)
            return redirect('core:pages_choose_juz')
        
        # غير كده: فلو الامتحان الأول كالعادة
        if ans and ans.isdigit() and int(ans) == correct_count:
            request.session['score'] = request.session.get('score', 0) + 1
        request.session['test_index'] = idx + 1
        return redirect('tests:similar_on_pages:question')
    
    # تجهيز نص العبارة للعرض
    phrase_txt = question.get('phrase_text') or question.get('phrase')
    if not phrase_txt:
        pid = question.get('phrase_id')
        if pid:
            try:
                phrase_txt = Phrase.objects.only('text').get(id=pid).text
            except Phrase.DoesNotExist:
                phrase_txt = ''
        else:
            phrase_txt = ''
    
    try:
        correct_count = int(question.get('correct_count'))
    except (TypeError, ValueError):
        correct_count = 2
    
    # إنشاء الخيارات
    test_service = TestService(student)
    options = test_service.make_options(correct_count)
    
    return render(request, 'core/test_question.html', {
        'student': student,
        'question_number': idx + 1, 'total_questions': total,
        'phrase': phrase_txt,
        'options': options,
        'scope_label': request.session.get('scope_label', ''),
        'progress_percent': progress,
        'correct_count': correct_count,
        'submitted': False,
        'hide_footer': True,
    })


@login_required
@require_POST
def report(request):
    """إبلاغ عن مشكلة في السؤال"""
    from core.views import report_question
    return report_question(request)
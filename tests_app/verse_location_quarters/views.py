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
    request.session['selected_test_type'] = 'verse_location_quarters'


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
            return redirect('tests:verse_location_quarters:selection')
        
        request.session.update({
            'selected_juz': sel_juz,
            'selected_quarters': sel_q,
            'num_questions': num_q,
            'difficulty': difficulty,
            'test_index': 0,
            'score': 0,
        })
        request.session.pop('scope_label', None)
        return redirect('tests:verse_location_quarters:start')
    
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
        'selected_test_type': request.session.get('selected_test_type', 'verse_location_quarters'),
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
        test_type='verse_location_quarters',
        selected_juz=juz_ids,
        selected_quarters=q_ids,
        num_questions=desired,
        difficulty=difficulty
    )
    
    # إنشاء الأسئلة
    questions = test_service.generate_verse_location_questions(session, desired, difficulty)
    
    if not questions:
        messages.error(request, "مافيش آيات كافية فى النطاق.")
        return redirect('tests:verse_location_quarters:selection')
    
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
    
    return redirect('tests:verse_location_quarters:question')


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
            TestSession.objects.filter(id=db_sid).update(completed=True)
        request.session['test_index'] = len(qs)
        return redirect('tests:verse_location_quarters:question')
    
    if request.method == 'POST':
        ans = request.POST.get('occurrence')
        # خزّن الإجابة في السيشن
        try:
            qs[idx]['given_answer'] = int(ans)
        except (ValueError, TypeError):
            qs[idx]['given_answer'] = None
        request.session['questions'] = qs
        
        # الصحيحة لهذا السؤال
        correct_quarter_id = question.get('correct_quarter_id')
        
        # سجّل الإجابة في الـDB حسب ترتيب السؤال
        db_qids = request.session.get('db_question_ids') or []
        if isinstance(db_qids, list) and idx < len(db_qids):
            given = qs[idx]['given_answer']
            is_corr = bool(given is not None and int(given) == correct_quarter_id)
            TestQuestion.objects.filter(id=db_qids[idx]).update(
                student_response=str(given if given is not None else ''),
                is_correct=is_corr
            )
        
        # فلو الامتحان العادي
        if ans and ans.isdigit() and int(ans) == correct_quarter_id:
            request.session['score'] = request.session.get('score', 0) + 1
        request.session['test_index'] = idx + 1
        return redirect('tests:verse_location_quarters:question')
    
    # تجهيز نص الآية للعرض
    ayah_text = question.get('ayah_text', '')
    surah = question.get('surah', 0)
    number = question.get('number', 0)
    
    # إنشاء نص السؤال
    question_text = f"في أي ربع توجد الآية: \"{ayah_text[:50]}{'...' if len(ayah_text) > 50 else ''}\"؟"
    
    # الحصول على الربع الصحيح
    correct_quarter_id = question.get('correct_quarter_id')
    
    # الحصول على الجلسة
    db_sid = request.session.get('db_session_id')
    session = TestSession.objects.get(id=db_sid) if db_sid else None
    
    # إنشاء خيارات الأرباع
    if session and session.quarters.exists():
        quarters = Quarter.objects.filter(id__in=session.quarters.values_list('id', flat=True))
    elif session and session.juzs.exists():
        quarters = Quarter.objects.filter(juz__number__in=session.juzs.values_list('number', flat=True))
    else:
        quarters = Quarter.objects.all()
    
    # تحويل إلى قائمة
    quarter_list = list(quarters.select_related('juz').order_by('juz__number', 'index_in_juz'))
    
    # إضافة الربع الصحيح إذا لم يكن موجودًا
    if correct_quarter_id:
        correct_quarter = Quarter.objects.get(id=correct_quarter_id)
        if correct_quarter not in quarter_list:
            quarter_list.append(correct_quarter)
    
    # إضافة بعض الأرباع الأخرى للاختيار
    if len(quarter_list) < 4:
        additional_quarters = Quarter.objects.exclude(id__in=[q.id for q in quarter_list]).select_related('juz').order_by('juz__number', 'index_in_juz')[:4-len(quarter_list)]
        quarter_list.extend(additional_quarters)
    
    # خلط الأرباع عشوائيًا
    import random
    random.shuffle(quarter_list)
    
    # إنشاء خيارات الأرباع
    options = []
    for quarter in quarter_list:
        options.append({
            'id': quarter.id,
            'label': f"{quarter.juz} - الربع {quarter.index_in_juz}",
            'is_correct': quarter.id == correct_quarter_id
        })
    
    # تقليل الخيارات إلى 4 فقط
    options = options[:4]
    
    return render(request, 'core/test_question.html', {
        'student': student,
        'question_number': idx + 1, 'total_questions': total,
        'phrase': question_text,
        'ayah_text': ayah_text,
        'surah': surah,
        'number': number,
        'options': options,
        'scope_label': request.session.get('scope_label', ''),
        'progress_percent': progress,
        'correct_count': correct_quarter_id,
        'submitted': False,
        'hide_footer': True,
        'test_type': 'verse_location_quarters',
    })


@login_required
@require_POST
def report(request):
    """إبلاغ عن مشكلة في السؤال"""
    from core.views import report_question
    return report_question(request)
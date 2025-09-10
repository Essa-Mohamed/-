from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Count
import math
import random

from core.models import Student, Juz, Quarter, Phrase, PhraseOccurrence, Ayah, TestSession, TestQuestion
from core.services.user_service import UserService
from tests_app.services.test_service import TestService


def get_surah_names():
    """إرجاع قاموس بأسماء السور"""
    return {
        1: "الفاتحة", 2: "البقرة", 3: "آل عمران", 4: "النساء", 5: "المائدة",
        6: "الأنعام", 7: "الأعراف", 8: "الأنفال", 9: "التوبة", 10: "يونس",
        11: "هود", 12: "يوسف", 13: "الرعد", 14: "إبراهيم", 15: "الحجر",
        16: "النحل", 17: "الإسراء", 18: "الكهف", 19: "مريم", 20: "طه",
        21: "الأنبياء", 22: "الحج", 23: "المؤمنون", 24: "النور", 25: "الفرقان",
        26: "الشعراء", 27: "النمل", 28: "القصص", 29: "العنكبوت", 30: "الروم",
        31: "لقمان", 32: "السجدة", 33: "الأحزاب", 34: "سبأ", 35: "فاطر",
        36: "يس", 37: "الصافات", 38: "ص", 39: "الزمر", 40: "غافر",
        41: "فصلت", 42: "الشورى", 43: "الزخرف", 44: "الدخان", 45: "الجاثية",
        46: "الأحقاف", 47: "محمد", 48: "الفتح", 49: "الحجرات", 50: "ق",
        51: "الذاريات", 52: "الطور", 53: "النجم", 54: "القمر", 55: "الرحمن",
        56: "الواقعة", 57: "الحديد", 58: "المجادلة", 59: "الحشر", 60: "الممتحنة",
        61: "الصف", 62: "الجمعة", 63: "المنافقون", 64: "التغابن", 65: "الطلاق",
        66: "التحريم", 67: "الملك", 68: "القلم", 69: "الحاقة", 70: "المعارج",
        71: "نوح", 72: "الجن", 73: "المزمل", 74: "المدثر", 75: "القيامة",
        76: "الإنسان", 77: "المرسلات", 78: "النبأ", 79: "النازعات", 80: "عبس",
        81: "التكوير", 82: "الانفطار", 83: "المطففين", 84: "الانشقاق", 85: "البروج",
        86: "الطارق", 87: "الأعلى", 88: "الغاشية", 89: "الفجر", 90: "البلد",
        91: "الشمس", 92: "الليل", 93: "الضحى", 94: "الشرح", 95: "التين",
        96: "العلق", 97: "القدر", 98: "البينة", 99: "الزلزلة", 100: "العاديات",
        101: "القارعة", 102: "التكاثر", 103: "العصر", 104: "الهمزة", 105: "الفيل",
        106: "قريش", 107: "الماعون", 108: "الكوثر", 109: "الكافرون", 110: "النصر",
        111: "المسد", 112: "الإخلاص", 113: "الفلق", 114: "الناس"
    }


def calculate_page_in_quarter(ayah_page, quarter_first_page):
    """حساب الصفحة داخل الربع"""
    return ayah_page - quarter_first_page + 1


def _ensure_type_in_session(request):
    """نثبت نوع الاختبار في السيشن"""
    request.session['selected_test_type'] = 'similar_positions_on_pages'


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
        
        # تشخيص: طباعة البيانات الواردة
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"DEBUG POST: sel_juz = {sel_juz}")
        logger.error(f"DEBUG POST: sel_q = {sel_q}")
        logger.error(f"DEBUG POST: request.POST = {dict(request.POST)}")
        
        try:
            num_q = int(request.POST.get('num_questions', 5))
        except ValueError:
            num_q = 5
        if num_q not in [5, 10, 15, 20]:
            num_q = 5
        
        difficulty = request.POST.get('difficulty', 'mixed')
        mandatory_order = request.POST.get('mandatory_order', 'false') == 'true'
        
        # تحويل الأجزاء والأرباع إلى أرقام
        sel_juz = [int(j) for j in sel_juz if str(j).isdigit()]
        sel_q = [int(q) for q in sel_q if str(q).isdigit()]
        
        # تشخيص: طباعة البيانات بعد التحويل
        logger.error(f"DEBUG POST after conversion: sel_juz = {sel_juz}")
        logger.error(f"DEBUG POST after conversion: sel_q = {sel_q}")
        
        # التحقق من وجود نطاق
        if not sel_juz and not sel_q:
            messages.error(request, "لازم تختار جزء أو رُبع.")
            return redirect('tests:similar_positions_on_pages:selection')
        
        # حفظ البيانات في الجلسة
        request.session.update({
            'selected_juz': sel_juz,
            'selected_quarters': sel_q,
            'num_questions': num_q,
            'difficulty': difficulty,
            'mandatory_order': mandatory_order,
            'test_index': 0,
            'score': 0,
            'bonus': 0,
        })
        request.session.pop('scope_label', None)
        return redirect('tests:similar_positions_on_pages:start')
    
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
        'selected_test_type': request.session.get('selected_test_type', 'similar_positions_on_pages'),
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
    mandatory_order = request.session.get('mandatory_order', False)
    
    # استخدام نفس منطق إنشاء الأسئلة من similar_count
    if q_ids: 
        ayat_qs = Ayah.objects.filter(quarter_id__in=q_ids)
    elif juz_ids: 
        ayat_qs = Ayah.objects.filter(quarter__juz__number__in=juz_ids)
    else: 
        messages.error(request, "مفيش نطاق محدد.")
        return redirect('tests:similar_positions_on_pages:selection')
    
    if not ayat_qs.exists(): 
        messages.error(request, "النطاق لا يحتوى آيات.")
        return redirect('tests:similar_positions_on_pages:selection')

    ayat_ids = list(ayat_qs.values_list('id', flat=True))
    MAX_OCC_SCOPE = 60
    
    # إحصائيات التكرار للنطاق
    stats = (PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids).values('phrase_id')
             .annotate(freq=Count('id')).filter(freq__gte=2, freq__lte=MAX_OCC_SCOPE))
    
    # فلتر إضافي: استبعاد العبارات القصيرة جداً
    phrase_ids = [s['phrase_id'] for s in stats]
    phrases = Phrase.objects.filter(id__in=phrase_ids)
    valid_phrase_ids = [p.id for p in phrases if p.length_words >= 3]
    
    if valid_phrase_ids:
        stats = stats.filter(phrase_id__in=valid_phrase_ids)
    
    # فلتر إضافي: استبعاد آيات بداية الأرباع
    quarter_start_ayah_ids = set()
    if q_ids:
        for quarter_id in q_ids:
            first_ayah = Ayah.objects.filter(quarter_id=quarter_id).order_by('surah', 'number').first()
            if first_ayah:
                quarter_start_ayah_ids.add(first_ayah.id)
    elif juz_ids:
        for juz_id in juz_ids:
            quarters = Quarter.objects.filter(juz__number=juz_id)
            for quarter in quarters:
                first_ayah = Ayah.objects.filter(quarter=quarter).order_by('surah', 'number').first()
                if first_ayah:
                    quarter_start_ayah_ids.add(first_ayah.id)
    
    if quarter_start_ayah_ids:
        quarter_start_phrases = set(PhraseOccurrence.objects.filter(ayah_id__in=quarter_start_ayah_ids).values_list('phrase_id', flat=True))
        other_ayah_ids = set(ayat_ids) - quarter_start_ayah_ids
        other_phrases = set(PhraseOccurrence.objects.filter(ayah_id__in=other_ayah_ids).values_list('phrase_id', flat=True))
        excluded_phrases = quarter_start_phrases - other_phrases
        if excluded_phrases:
            stats = stats.exclude(phrase_id__in=excluded_phrases)
    
    if not stats: 
        stats_loose = (PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids).values('phrase_id')
                      .annotate(freq=Count('id')).filter(freq__gte=2))
        if not stats_loose:
            messages.error(request, "مافيش عبارات متشابهة كافية فى النطاق المحدد.")
            return redirect('tests:similar_positions_on_pages:selection')
        else:
            stats = stats_loose

    phrase_ids = [s['phrase_id'] for s in stats]
    freq_map = {s['phrase_id']: s['freq'] for s in stats}
    
    occ_rows = PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids, phrase_id__in=phrase_ids).values('phrase_id', 'ayah_id')
    occ_by_phrase = {}
    for r in occ_rows: 
        occ_by_phrase.setdefault(r['phrase_id'], set()).add(r['ayah_id'])
    
    phrases = {p.id: p for p in Phrase.objects.filter(id__in=phrase_ids)}
    sorted_pids = sorted(phrase_ids, key=lambda pid: (-phrases[pid].length_words, -freq_map[pid], phrases[pid].text))
    
    kept, kept_sets = [], []
    for pid in sorted_pids:
        aset = occ_by_phrase[pid]
        if any(aset.issubset(S) for S in kept_sets): 
            continue
        kept.append(pid)
        kept_sets.append(aset)

    def bucket(ph_len, freq):
        if ph_len >= 5 and 2 <= freq <= 3: 
            return 'easy'
        if ph_len >= 4 and 2 <= freq <= 6: 
            return 'medium'
        if ph_len >= 3 and 7 <= freq <= 60: 
            return 'hard'
        return 'other'

    candidates = []
    for pid in kept:
        ph = phrases[pid]
        freq = freq_map[pid]
        b = bucket(ph.length_words, freq)
        if b == 'other': 
            continue
        
        # الحصول على جميع التكرارات الفردية للعبارة في النطاق
        phrase_occurrences = PhraseOccurrence.objects.filter(
            phrase_id=pid, 
            ayah_id__in=ayat_ids
        ).select_related('ayah__quarter__juz').order_by('ayah__surah', 'ayah__number', 'start_word')
        
        surah_names = get_surah_names()
        literal = []
        # تجميع التكرارات حسب الآية
        ayah_occurrences = {}
        for occ in phrase_occurrences:
            ayah_key = f"{occ.ayah.surah}:{occ.ayah.number}"
            if ayah_key not in ayah_occurrences:
                ayah_occurrences[ayah_key] = {
                    'ayah': occ.ayah,
                    'positions': []
                }
            ayah_occurrences[ayah_key]['positions'].append({
                'start_word': occ.start_word,
                'end_word': occ.end_word
            })
        
        # إنشاء البيانات للعرض
        for ayah_key, data in ayah_occurrences.items():
            ayah = data['ayah']
            literal.append({
                'surah': ayah.surah, 
                'surah_name': surah_names.get(ayah.surah, f"سورة {ayah.surah}"), 
                'number': ayah.number, 
                'juz_number': ayah.quarter.juz.number if ayah.quarter else None, 
                'quarter_label': ayah.quarter.label if ayah.quarter else None, 
                'text': ayah.text,
                'positions': data['positions'],
                'count': len(data['positions']),
                'ayah_id': ayah.id,
                'quarter_id': ayah.quarter.id if ayah.quarter else None,
                'page_number': ayah.page.number if ayah.page else None
            })
        candidates.append({
            'phrase_id': pid, 
            'phrase_text': ph.text, 
            'correct_count': freq, 
            'occurrence_ayah_ids': list(occ_by_phrase[pid]), 
            'literal_ayahs': literal, 
            'bucket': b, 
            'score': freq * math.log(1 + ph.length_words)
        })

    if not candidates: 
        for pid in kept:
            ph = phrases[pid]
            freq = freq_map[pid]
            
            phrase_occurrences = PhraseOccurrence.objects.filter(
                phrase_id=pid, 
                ayah_id__in=ayat_ids
            ).select_related('ayah__quarter__juz').order_by('ayah__surah', 'ayah__number', 'start_word')
            
            surah_names = get_surah_names()
            literal = []
            ayah_occurrences = {}
            for occ in phrase_occurrences:
                ayah_key = f"{occ.ayah.surah}:{occ.ayah.number}"
                if ayah_key not in ayah_occurrences:
                    ayah_occurrences[ayah_key] = {
                        'ayah': occ.ayah,
                        'positions': []
                    }
                ayah_occurrences[ayah_key]['positions'].append({
                    'start_word': occ.start_word,
                    'end_word': occ.end_word
                })
            
            for ayah_key, data in ayah_occurrences.items():
                ayah = data['ayah']
                literal.append({
                    'surah': ayah.surah, 
                    'surah_name': surah_names.get(ayah.surah, f"سورة {ayah.surah}"), 
                    'number': ayah.number, 
                    'juz_number': ayah.quarter.juz.number if ayah.quarter else None, 
                    'quarter_label': ayah.quarter.label if ayah.quarter else None, 
                    'text': ayah.text,
                    'positions': data['positions'],
                    'count': len(data['positions']),
                    'ayah_id': ayah.id,
                    'quarter_id': ayah.quarter.id if ayah.quarter else None,
                    'page_number': ayah.page.number if ayah.page else None
                })
            candidates.append({
                'phrase_id': pid,
                'phrase_text': ph.text,
                'correct_count': freq,
                'occurrence_ayah_ids': list(occ_by_phrase[pid]),
                'literal_ayahs': literal,
                'bucket': 'easy',
                'score': freq * math.log(1 + ph.length_words),
            })

    if not candidates:
        messages.error(request, "لا توجد أسئلة مناسبة لهذا المستوى في النطاق.")
        return redirect('tests:similar_positions_on_pages:selection')

    # اختيار نهائي
    if difficulty == 'mixed':
        E = [c for c in candidates if c['bucket'] == 'easy']
        M = [c for c in candidates if c['bucket'] == 'medium']
        H = [c for c in candidates if c['bucket'] == 'hard']
        random.shuffle(E)
        random.shuffle(M)
        random.shuffle(H)
        
        ne = max(0, round(desired * 0.40))
        nm = max(0, round(desired * 0.45))
        nh = max(0, desired - ne - nm)
        
        take = E[:ne] + M[:nm] + H[:nh]
        for pool in [M[nm:], E[ne:], H[nh:]]:
            if len(take) >= desired:
                break
            need = desired - len(take)
            take += pool[:need]
        selected = take[:desired]
        random.shuffle(selected)
    else:
        filtered = [c for c in candidates if c['bucket'] == difficulty]
        if not filtered:
            filtered = candidates
        if not filtered:
            messages.error(request, "لا توجد أسئلة مناسبة لهذا المستوى في النطاق.")
            return redirect('tests:similar_positions_on_pages:selection')
        filtered.sort(key=lambda x: (-x['score'], x['phrase_text']))
        selected = filtered[:desired]

    # إنشاء الأسئلة
    questions = []
    for c in selected:
        question_data = {
            'phrase_id': c['phrase_id'], 
            'phrase_text': c['phrase_text'], 
            'correct_count': c['correct_count'], 
            'occurrence_ayah_ids': c['occurrence_ayah_ids'], 
            'literal_ayahs': c['literal_ayahs'], 
            'given_answer': None,
            'positions_answered': [],  # المواضع التي تم الإجابة عليها
            'positions_correct': [],  # المواضع الصحيحة
            'positions_wrong': [],    # المواضع الخاطئة
        }
        questions.append(question_data)
    
    # إنشاء جلسة الاختبار
    test_service = TestService(student)
    session = test_service.create_test_session(
        test_type='similar_positions_on_pages',
        selected_juz=juz_ids,
        selected_quarters=q_ids,
        num_questions=len(questions),
        difficulty=difficulty
    )
    
    # حفظ الأسئلة في الجلسة
    request.session['questions'] = questions
    request.session['test_index'] = 0
    request.session['score'] = 0
    request.session['bonus'] = 0
    request.session['db_session_id'] = session.id
    request.session['scope_label'] = test_service.build_scope_label(juz_ids, q_ids)
    
    # إنشاء أسئلة في قاعدة البيانات للتتبع
    db_qids = []
    for _ in questions:
        tq = TestQuestion.objects.create(session=session)
        db_qids.append(tq.id)
    request.session['db_question_ids'] = db_qids
    
    return redirect('tests:similar_positions_on_pages:question')


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
        return redirect('tests:similar_positions_on_pages:result')
    
    question = qs[idx]
    progress = round((idx + 1) / total * 100) if total else 0
    
    # إنهاء مبكر
    if request.method == 'POST' and request.POST.get('action') == 'end':
        return redirect('tests:similar_positions_on_pages:result')
    
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
        
        # التحقق من صحة الإجابة
        if ans and ans.isdigit() and int(ans) > 0:
            # انتقل لصفحة المواضع بغض النظر عن صحة الإجابة
            request.session['positions_flow'] = {
                'q_index': idx,
                'target_total': int(ans),
                'current': 1,
                'answered_positions': [],
                'correct_positions': [],
                'wrong_positions': [],
                'correct_count': correct_count,  # حفظ العدد الصحيح للمقارنة
            }
            return redirect('tests:similar_positions_on_pages:position')
        else:
            # لو لم يختر عدد المواضع، انتقل للسؤال التالي
            request.session['test_index'] = idx + 1
            return redirect('tests:similar_positions_on_pages:question')
    
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
    
    return render(request, 'tests_app/similar_positions_on_pages/question.html', {
        'student': student,
        'current_index': idx,
        'total_questions': total,
        'question': {
            'phrase': {'text': phrase_txt},
            'correct_answer': correct_count
        },
        'options': options,
        'scope_label': request.session.get('scope_label', ''),
        'progress_percent': progress,
        'correct_count': correct_count,
        'submitted': False,
        'hide_footer': True,
        'feedback': None,
        'is_correct': None,
    })


@login_required
def position(request):
    """صفحة اختيار موضع العبارة"""
    _ensure_type_in_session(request)
    
    # الحصول على الطالب
    user_service = UserService()
    student = user_service.get_or_create_student(request.user)
    
    positions_flow = request.session.get('positions_flow', {})
    q_index = positions_flow.get('q_index', 0)
    current_pos = positions_flow.get('current', 1)
    target_total = positions_flow.get('target_total', 0)
    mandatory_order = request.session.get('mandatory_order', False)
    
    qs = request.session.get('questions', [])
    if q_index >= len(qs):
        return redirect('tests:similar_positions_on_pages:result')
    
    question = qs[q_index]
    
    # انتهت المواضع لهذا السؤال؟
    if current_pos > target_total:
        # احسب النقاط لهذا السؤال
        correct_positions = positions_flow.get('correct_positions', [])
        wrong_positions = positions_flow.get('wrong_positions', [])
        
        # حساب النقاط (كل موضع صحيح = 100/عدد المواضع)
        points_per_position = 100 / target_total if target_total > 0 else 0
        question_score = len(correct_positions) * points_per_position
        
        # تحديث بيانات السؤال
        question['positions_answered'] = positions_flow.get('answered_positions', [])
        question['positions_correct'] = correct_positions
        question['positions_wrong'] = wrong_positions
        question['question_score'] = question_score
        
        # تحديث النقاط الإجمالية
        current_score = request.session.get('score', 0)
        request.session['score'] = current_score + question_score
        
        # تنظيف بيانات المواضع
        request.session.pop('positions_flow', None)
        
        # الانتقال للسؤال التالي
        request.session['test_index'] = q_index + 1
        return redirect('tests:similar_positions_on_pages:question')
    
    # معالجة الإجابة
    if request.method == 'POST':
        juz_id = request.POST.get('juz_id')
        quarter_id = request.POST.get('quarter_id')
        page_in_quarter = request.POST.get('page_in_quarter')
        
        if juz_id and quarter_id and page_in_quarter:
            try:
                juz_id = int(juz_id)
                quarter_id = int(quarter_id)
                page_in_quarter = int(page_in_quarter)
                
                # التحقق من صحة الإجابة
                correct = False
                try:
                    quarter = Quarter.objects.get(id=quarter_id)
                    first_page = quarter.first_page
                    expected_page = first_page + page_in_quarter - 1
                    
                    for ayah_data in question.get('literal_ayahs', []):
                        if (ayah_data.get('juz_number') == juz_id and 
                            ayah_data.get('quarter_id') == quarter_id and
                            ayah_data.get('page_number') == expected_page):
                            correct = True
                            break
                except Quarter.DoesNotExist:
                    correct = False
                
                # حفظ الإجابة
                answered_positions = positions_flow.get('answered_positions', [])
                answered_positions.append({
                    'position': current_pos,
                    'juz_id': juz_id,
                    'quarter_id': quarter_id,
                    'page_in_quarter': page_in_quarter,
                    'correct': correct
                })
                
                if correct:
                    correct_positions = positions_flow.get('correct_positions', [])
                    correct_positions.append(current_pos)
                    positions_flow['correct_positions'] = correct_positions
                else:
                    wrong_positions = positions_flow.get('wrong_positions', [])
                    wrong_positions.append(current_pos)
                    positions_flow['wrong_positions'] = wrong_positions
                
                positions_flow['answered_positions'] = answered_positions
                positions_flow['current'] = current_pos + 1
                request.session['positions_flow'] = positions_flow
                
                # إذا كان الترتيب إجباري، انتقل للموضع التالي
                if mandatory_order:
                    return redirect('tests:similar_positions_on_pages:position')
                else:
                    # إذا لم يكن إجباري، أعد تحميل الصفحة لاختيار موضع آخر
                    return redirect('tests:similar_positions_on_pages:position')
                    
            except (ValueError, Quarter.DoesNotExist):
                messages.error(request, "خطأ في البيانات المرسلة.")
    
    # تجهيز البيانات للعرض
    juz_list = Juz.objects.all().order_by('number')
    juz_options = [{'id': j.number, 'name': f"الجزء {j.number}"} for j in juz_list]
    
    # إضافة أسماء الأجزاء
    juz_names = {
        1: "الفاتحة", 2: "البقرة", 3: "آل عمران", 4: "النساء", 5: "المائدة",
        6: "الأنعام", 7: "الأعراف", 8: "الأنفال", 9: "التوبة", 10: "يونس",
        11: "هود", 12: "يوسف", 13: "الرعد", 14: "إبراهيم", 15: "الحجر",
        16: "النحل", 17: "الإسراء", 18: "الكهف", 19: "مريم", 20: "طه",
        21: "الأنبياء", 22: "الحج", 23: "المؤمنون", 24: "النور", 25: "الفرقان",
        26: "الشعراء", 27: "النمل", 28: "القصص", 29: "العنكبوت", 30: "الروم",
        31: "لقمان", 32: "السجدة", 33: "الأحزاب", 34: "سبأ", 35: "فاطر",
        36: "يس", 37: "الصافات", 38: "ص", 39: "الزمر", 40: "غافر",
        41: "فصلت", 42: "الشورى", 43: "الزخرف", 44: "الدخان", 45: "الجاثية",
        46: "الأحقاف", 47: "محمد", 48: "الفتح", 49: "الحجرات", 50: "ق",
        51: "الذاريات", 52: "الطور", 53: "النجم", 54: "القمر", 55: "الرحمن",
        56: "الواقعة", 57: "الحديد", 58: "المجادلة", 59: "الحشر", 60: "الممتحنة",
        61: "الصف", 62: "الجمعة", 63: "المنافقون", 64: "التغابن", 65: "الطلاق",
        66: "التحريم", 67: "الملك", 68: "القلم", 69: "الحاقة", 70: "المعارج",
        71: "نوح", 72: "الجن", 73: "المزمل", 74: "المدثر", 75: "القيامة",
        76: "الإنسان", 77: "المرسلات", 78: "النبأ", 79: "النازعات", 80: "عبس",
        81: "التكوير", 82: "الانفطار", 83: "المطففين", 84: "الانشقاق", 85: "البروج",
        86: "الطارق", 87: "الأعلى", 88: "الغاشية", 89: "الفجر", 90: "البلد",
        91: "الشمس", 92: "الليل", 93: "الضحى", 94: "الشرح", 95: "التين",
        96: "العلق", 97: "القدر", 98: "البينة", 99: "الزلزلة", 100: "العاديات",
        101: "القارعة", 102: "التكاثر", 103: "العصر", 104: "الهمزة", 105: "الفيل",
        106: "قريش", 107: "الماعون", 108: "الكوثر", 109: "الكافرون", 110: "النصر",
        111: "المسد", 112: "الإخلاص", 113: "الفلق", 114: "الناس"
    }
    
    # تحديث أسماء الأجزاء
    for juz_option in juz_options:
        juz_number = juz_option['id']
        if juz_number in juz_names:
            juz_option['name'] = f"الجزء {juz_number} - {juz_names[juz_number]}"
    
    # تجهيز بيانات الأرباع
    quarter_options = []
    for juz in juz_list:
        quarters = Quarter.objects.filter(juz=juz).order_by('index_in_juz')
        for quarter in quarters:
            quarter_options.append({
                'id': quarter.id,
                'name': quarter.label,
                'juz_id': juz.number
            })
    
    # طباعة البيانات للتشخيص
    print(f"DEBUG: quarter_options = {quarter_options}")
    print(f"DEBUG: juz_options = {juz_options}")
    print(f"DEBUG: quarter_options length = {len(quarter_options)}")
    
    # طباعة عينة من الأرباع
    for i, q in enumerate(quarter_options[:5]):
        print(f"DEBUG: quarter {i}: {q}")
    
    # التحقق من وجود أرباع
    if not quarter_options:
        print("WARNING: No quarters found!")
        # إنشاء أرباع افتراضية للاختبار
        quarter_options = []
        for juz in juz_list:
            for i in range(1, 5):  # 4 أرباع لكل جزء
                quarter_options.append({
                    'id': f"{juz.number}_{i}",
                    'name': f"الربع {i}",
                    'juz_id': juz.number
                })
        print(f"DEBUG: Created default quarters = {quarter_options}")
    
    # إذا تم اختيار الجزء، جلب الأرباع
    selected_juz_id = None
    if request.method == 'GET' and 'juz_id' in request.GET:
        try:
            selected_juz_id = int(request.GET.get('juz_id'))
        except (ValueError, TypeError):
            pass
    elif request.method == 'POST':
        # إذا كان POST، جلب الأرباع من البيانات المرسلة
        juz_id = request.POST.get('juz_id')
        if juz_id:
            try:
                selected_juz_id = int(juz_id)
            except (ValueError, TypeError):
                pass
    
    # تحويل البيانات إلى JSON
    import json
    quarter_options_json = json.dumps(quarter_options, ensure_ascii=False)
    juz_options_json = json.dumps(juz_options, ensure_ascii=False)
    
    return render(request, 'tests_app/similar_positions_on_pages/position.html', {
        'student': student,
        'question': question,
        'current_index': q_index,
        'total_questions': len(qs),
        'position_index': current_pos - 1,
        'total_positions': target_total,
        'juz_options': juz_options,
        'quarter_options': quarter_options,
        'quarter_options_json': quarter_options_json,
        'juz_options_json': juz_options_json,
        'selected_juz_id': selected_juz_id,
        'mandatory_order': mandatory_order,
        'answered_positions': positions_flow.get('answered_positions', []),
        'hide_footer': True,
    })


@login_required
def result(request):
    """صفحة عرض النتائج"""
    _ensure_type_in_session(request)
    
    # الحصول على الطالب
    user_service = UserService()
    student = user_service.get_or_create_student(request.user)
    
    # جلب بيانات النتائج
    qs = request.session.get('questions', [])
    total_questions = len(qs)
    score = request.session.get('score', 0)
    bonus = request.session.get('bonus', 0)
    mandatory_order = request.session.get('mandatory_order', False)
    
    # حساب البونص إذا كان الترتيب إجباري
    if mandatory_order and total_questions > 0:
        bonus = total_questions * 10  # 10 نقاط بونص لكل سؤال
        request.session['bonus'] = bonus
    
    final_score = score + bonus
    
    # تفاصيل النتائج
    detailed_results = []
    for i, q in enumerate(qs):
        detailed_results.append({
            'question_number': i + 1,
            'phrase': q.get('phrase_text', ''),
            'correct_count': q.get('correct_count', 0),
            'given_answer': q.get('given_answer', 0),
            'positions_answered': q.get('positions_answered', []),
            'positions_correct': q.get('positions_correct', []),
            'positions_wrong': q.get('positions_wrong', []),
            'question_score': q.get('question_score', 0),
        })
    
    # علّم الجلسة كمكتملة
    db_sid = request.session.get('db_session_id')
    if db_sid:
        from django.utils import timezone
        TestSession.objects.filter(id=db_sid).update(
            completed=True,
            completed_at=timezone.now()
        )
    
    # تنظيف السيشن
    for k in ['questions', 'test_index', 'score', 'bonus', 'selected_juz', 'selected_quarters',
              'num_questions', 'scope_label', 'difficulty', 'mandatory_order', 'db_session_id', 'db_question_ids', 'positions_flow']:
        request.session.pop(k, None)
    
    return render(request, 'tests_app/similar_positions_on_pages/result.html', {
        'student': student,
        'score': score,
        'bonus': bonus,
        'final_score': final_score,
        'total_questions': total_questions,
        'detailed_results': detailed_results,
        'scope_label': request.session.get('scope_label', ''),
        'mandatory_order': mandatory_order,
        'hide_footer': True,
    })


@login_required
@require_POST
def report(request):
    """إبلاغ عن مشكلة في السؤال"""
    from core.views import report_question
    return report_question(request)

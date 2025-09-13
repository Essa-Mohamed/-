from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Count
import math
import random

from students.models import Student
from quran_structure.models import Juz, Quarter, Ayah
from testing.models import TestSession, TestQuestion
from core.models import Phrase, PhraseOccurrence
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


def _ensure_type_in_session(request):
    # نثبت نوع الاختبار في السيشن لضمان سلوك المنطق الحالي
    request.session['selected_test_type'] = 'similar_count'


@login_required
def selection(request):
    """صفحة اختيار النطاق للاختبار"""
    _ensure_type_in_session(request)
    
    # الحصول على الطالب
    user_service = UserService()
    student = user_service.get_or_create_student(request.user)
    
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
        'selected_test_type': request.session.get('selected_test_type', 'similar_count'),
    })


@login_required
def start(request):
    """بدء الاختبار وإنشاء الأسئلة"""
    _ensure_type_in_session(request)
    
    # الحصول على الطالب
    user_service = UserService()
    student = user_service.get_or_create_student(request.user)
    
    # الحصول على البيانات من POST أو من الجلسة
    if request.method == 'POST':
        # البيانات تأتي من القالب مباشرة
        sel_juz = request.POST.getlist('selected_juz')
        sel_q = request.POST.getlist('selected_quarters')
        try:
            num_q = int(request.POST.get('num_questions', 5))
        except ValueError:
            num_q = 5
        if num_q not in [5, 10, 15, 20]:
            num_q = 5
        
        difficulty = request.POST.get('difficulty', 'mixed')
        
        # تشخيص: طباعة البيانات الواردة
        print(f"DEBUG POST: sel_juz = {sel_juz}")
        print(f"DEBUG POST: sel_q = {sel_q}")
        print(f"DEBUG POST: num_q = {num_q}")
        print(f"DEBUG POST: difficulty = {difficulty}")
        
        sel_juz = [int(j) for j in sel_juz if str(j).isdigit()]
        sel_q = [int(q) for q in sel_q if str(q).isdigit()]
        
        # تشخيص: طباعة البيانات بعد التحويل
        print(f"DEBUG POST after conversion: sel_juz = {sel_juz}")
        print(f"DEBUG POST after conversion: sel_q = {sel_q}")
        
        if not sel_juz and not sel_q:
            messages.error(request, "لازم تختار جزء أو رُبع.")
            return redirect('tests:similar_count:selection')
        
        # حفظ البيانات في الجلسة
        request.session.update({
            'selected_juz': sel_juz,
            'selected_quarters': sel_q,
            'num_questions': num_q,
            'difficulty': difficulty,
            'test_index': 0,
            'score': 0,
        })
        request.session.pop('scope_label', None)
        
        juz_ids = sel_juz
        q_ids = sel_q
        desired = num_q
    else:
        # البيانات تأتي من الجلسة (للانتقالات الداخلية)
        juz_ids = request.session.get('selected_juz', [])
        q_ids = request.session.get('selected_quarters', [])
        desired = int(request.session.get('num_questions', 5))
        difficulty = request.session.get('difficulty', 'mixed')
        
        # تشخيص: طباعة البيانات
        print(f"DEBUG SESSION: juz_ids = {juz_ids}")
        print(f"DEBUG SESSION: q_ids = {q_ids}")
        print(f"DEBUG SESSION: desired = {desired}")
        print(f"DEBUG SESSION: difficulty = {difficulty}")
    
    # استخدام المنطق المباشر من core/views.py
    if q_ids: 
        ayat_qs = Ayah.objects.filter(quarter_id__in=q_ids)
        print(f"DEBUG: Using quarters, found {ayat_qs.count()} ayahs")
    elif juz_ids: 
        ayat_qs = Ayah.objects.filter(quarter__juz__number__in=juz_ids)
        print(f"DEBUG: Using juzs, found {ayat_qs.count()} ayahs")
    else: 
        print("DEBUG: No juz_ids or q_ids found")
        messages.error(request, "مفيش نطاق محدد.")
        return redirect('tests:similar_count:selection')
    
    if not ayat_qs.exists(): 
        messages.error(request, "النطاق لا يحتوى آيات.")
        return redirect('tests:similar_count:selection')

    ayat_ids = list(ayat_qs.values_list('id', flat=True))
    MAX_OCC_SCOPE = 60
    
    # إحصائيات التكرار للنطاق
    stats = (PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids).values('phrase_id')
             .annotate(freq=Count('id')).filter(freq__gte=2, freq__lte=MAX_OCC_SCOPE))
    
    # فلتر إضافي: استبعاد العبارات القصيرة جداً (أقل من 3 كلمات)
    # هذه العبارات غالباً ما تكون كلمات شائعة وليست متشابهات حقيقية
    phrase_ids = [s['phrase_id'] for s in stats]
    phrases = Phrase.objects.filter(id__in=phrase_ids)
    valid_phrase_ids = [p.id for p in phrases if p.length_words >= 3]
    
    if valid_phrase_ids:
        stats = stats.filter(phrase_id__in=valid_phrase_ids)
    
    # فلتر إضافي: استبعاد آيات بداية الأرباع (الآيات الأولى في كل ربع)
    # هذه الآيات غالباً ما تحتوي على عبارات تظهر مرتين ولكنها ليست متشابهات حقيقية
    quarter_start_ayah_ids = set()
    if q_ids:
        # إذا كان الاختيار حسب الأرباع، استبعد الآيات الأولى في كل ربع
        for quarter_id in q_ids:
            first_ayah = Ayah.objects.filter(quarter_id=quarter_id).order_by('surah', 'number').first()
            if first_ayah:
                quarter_start_ayah_ids.add(first_ayah.id)
    elif juz_ids:
        # إذا كان الاختيار حسب الأجزاء، استبعد الآيات الأولى في كل ربع
        for juz_id in juz_ids:
            quarters = Quarter.objects.filter(juz__number=juz_id)
            for quarter in quarters:
                first_ayah = Ayah.objects.filter(quarter=quarter).order_by('surah', 'number').first()
                if first_ayah:
                    quarter_start_ayah_ids.add(first_ayah.id)
    
    # فلتر العبارات التي تظهر فقط في آيات بداية الأرباع
    if quarter_start_ayah_ids:
        # العبارات التي تظهر في آيات بداية الأرباع فقط
        quarter_start_phrases = set(PhraseOccurrence.objects.filter(ayah_id__in=quarter_start_ayah_ids).values_list('phrase_id', flat=True))
        # العبارات التي تظهر في آيات أخرى (غير بداية الأرباع)
        other_ayah_ids = set(ayat_ids) - quarter_start_ayah_ids
        other_phrases = set(PhraseOccurrence.objects.filter(ayah_id__in=other_ayah_ids).values_list('phrase_id', flat=True))
        # استبعاد العبارات التي تظهر فقط في آيات بداية الأرباع
        excluded_phrases = quarter_start_phrases - other_phrases
        if excluded_phrases:
            stats = stats.exclude(phrase_id__in=excluded_phrases)
    
    if not stats: 
        # محاولة البحث مع معايير أقل صرامة
        stats_loose = (PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids).values('phrase_id')
                      .annotate(freq=Count('id')).filter(freq__gte=2))
        if not stats_loose:
            messages.error(request, "مافيش عبارات متشابهة كافية فى النطاق المحدد. جرب نطاق أوسع أو أجزاء مختلفة.")
            return redirect('tests:similar_count:selection')
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
                'positions': data['positions'],  # قائمة بمواضع التكرارات في هذه الآية
                'count': len(data['positions'])  # عدد التكرارات في هذه الآية
            })
        candidates.append({'phrase_id': pid, 'phrase_text': ph.text, 'correct_count': freq, 'occurrence_ayah_ids': list(occ_by_phrase[pid]), 'literal_ayahs': literal, 'bucket': b, 'score': freq * math.log(1 + ph.length_words)})

    if not candidates: 
        # محاولة البحث بمعايير أقل صرامة
        for pid in kept:
            ph = phrases[pid]
            freq = freq_map[pid]
            # قبول جميع العبارات بغض النظر عن مستوى الصعوبة
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
                    'positions': data['positions'],  # قائمة بمواضع التكرارات في هذه الآية
                    'count': len(data['positions'])  # عدد التكرارات في هذه الآية
                })
            candidates.append({
                'phrase_id': pid,
                'phrase_text': ph.text,
                'correct_count': freq,
                'occurrence_ayah_ids': list(occ_by_phrase[pid]),
                'literal_ayahs': literal,
                'bucket': 'easy',  # افتراضي
                'score': freq * math.log(1 + ph.length_words),
            })

    if not candidates:
        messages.error(request, "لا توجد أسئلة مناسبة لهذا المستوى في النطاق.")
        return redirect('tests:similar_count:selection')

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
            return redirect('tests:similar_count:selection')
        filtered.sort(key=lambda x: (-x['score'], x['phrase_text']))
        selected = filtered[:desired]

    # إنشاء الأسئلة
    questions = [{'phrase_id': c['phrase_id'], 'phrase_text': c['phrase_text'], 'correct_count': c['correct_count'], 'occurrence_ayah_ids': c['occurrence_ayah_ids'], 'literal_ayahs': c['literal_ayahs'], 'given_answer': None} for c in selected]
    
    # إنشاء جلسة الاختبار
    test_service = TestService(student)
    session = test_service.create_test_session(
        test_type='similar_count',
        selected_juz=juz_ids,
        selected_quarters=q_ids,
        num_questions=len(questions),
        difficulty=difficulty
    )
    
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
    
    return redirect('tests:similar_count:question')


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
        detailed = []
        for q in qs:
            occurrences = q.get('literal_ayahs', [])
            # حساب إجمالي عدد التكرارات
            total_occurrences = sum(item.get('count', 1) for item in occurrences)
            detailed.append({
                'phrase': q.get('phrase_text') or q.get('phrase', ''),
                'correct_count': q.get('correct_count'),
                'given_answer': q.get('given_answer'),
                'occurrences': occurrences,
                'total_occurrences': total_occurrences,  # إجمالي عدد التكرارات
            })
        wrong = max(0, total - score)
        
        # علّم الجلسة كمكتملة
        db_sid = request.session.get('db_session_id')
        if db_sid:
            from django.utils import timezone
            TestSession.objects.filter(id=db_sid).update(
                completed=True,
                completed_at=timezone.now()
            )
        
        # حفظ بيانات النتائج في السيشن للعرض في صفحة منفصلة
        request.session['test_results'] = {
            'student_id': student.id,
            'score': score,
            'total': total,
            'detailed_results': detailed,
            'scope_label': scope_lbl,
            'wrong': wrong,
            'test_type': 'similar_count'
        }
        
        # نظّف السيشن
        for k in ['questions', 'test_index', 'score', 'selected_juz', 'selected_quarters',
                  'num_questions', 'scope_label', 'difficulty', 'db_session_id', 'db_question_ids']:
            request.session.pop(k, None)
        
        return redirect('tests:similar_count:result')
    
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
        # توجيه لصفحة النتائج بدلاً من إعادة توجيه للسؤال
        return redirect('tests:similar_count:question')
    
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
        
        # فلو الامتحان العادي
        if ans and ans.isdigit() and int(ans) == correct_count:
            request.session['score'] = request.session.get('score', 0) + 1
        request.session['test_index'] = idx + 1
        return redirect('tests:similar_count:question')
    
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
def result(request):
    """صفحة عرض النتائج"""
    _ensure_type_in_session(request)
    
    # جلب بيانات النتائج من السيشن
    results_data = request.session.get('test_results')
    if not results_data:
        # لو مفيش نتائج، نعيد للاختيار
        return redirect('tests:similar_count:selection')
    
    # جلب بيانات الطالب
    user_service = UserService()
    student = user_service.get_or_create_student(request.user)
    
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


@login_required
@require_POST
def report(request):
    """إبلاغ عن مشكلة في السؤال"""
    from core.views import report_question
    return report_question(request)



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Count, Sum, Q
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from .forms import AccountForm, PasswordChangeTightForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.http import JsonResponse
from .models import Ayah, Page
from django.conf import settings
from django.http import FileResponse, Http404
import os
from django.db.models import Exists, OuterRef



import math, random, re, unicodedata

from django.views.decorators.http import require_POST
from .models import (
    Student, Complaint, Juz, Quarter, SimilarityGroup, Ayah,
    Phrase, PhraseOccurrence, TestSession, TestQuestion
)


# ===== Helpers for ordinals and occurrence mapping =====
AR_ORD = {1:"الأول",2:"الثاني",3:"الثالث",4:"الرابع",5:"الخامس",6:"السادس",7:"السابع",8:"الثامن",9:"التاسع",10:"العاشر"}
def ar_ordinal(n:int) -> str:
    return f"{AR_ORD.get(n, n)}"

# ===== Scoring engine for "similar_on_pages" =====
# نسب البونص والخصم (تقدر تعدّلها لو حابب لاحقًا)
PAGES_BONUS_ORDER = 15                # بونص تفعيل "اختيار بالترتيب"
PENALTY_WRONG_JUZ_OTHER = 8           # خصم: اختيار جزء يخص موضع آخر
PENALTY_WRONG_QUARTER_OTHER = 6       # خصم: اختيار ربع يخص موضع آخر
PENALTY_EMPTY_JUZ = 5                 # خصم: لا يوجد أي موضع في هذا الجزء
PENALTY_EMPTY_QUARTER = 4             # خصم: لا يوجد أي موضع في هذا الربع
FAIL_THRESHOLD = 50                   # (اختياري) حد الرسوب إن احتجته في الواجهة

def _grade_state(request):
    """
    حالة الدرجة لامتحان 'مواضع المتشابهات في الصفحات':
    - bonus: مجموع البونصات
    - penalty: مجموع الخصومات
    - events: أحدث الأحداث (نص + نسبة +/-)
    - order_set: هل تم تفعيل "بالترتيب" مرة واحدة؟
    """
    st = request.session.get('pages_grade') or {}
    st.setdefault('bonus', 0)
    st.setdefault('penalty', 0)
    st.setdefault('events', [])
    st.setdefault('order_set', False)
    request.session['pages_grade'] = st
    return st

def _grade_push(request, text: str, delta: int):
    """
    يضيف حدثًا جديدًا ويحدث الدرجة.
    delta موجب للبونص، وسالب للخصم (مثلاً -6).
    """
    st = _grade_state(request)
    if delta >= 0:
        st['bonus'] = min(100, int(st.get('bonus', 0)) + int(delta))
    else:
        st['penalty'] = min(100, int(st.get('penalty', 0)) + int(-delta))
    st['events'].insert(0, {'t': text, 'd': int(delta)})
    request.session['pages_grade'] = st
    score = max(0, min(100, 100 - int(st['penalty']) + int(st['bonus'])))
    return int(score), int(delta)

def _grade_get(request):
    """
    يرجّع الدرجة الحالية + الحالة كاملة (للاستفادة في التمپليت).
    """
    st = _grade_state(request)
    score = max(0, min(100, 100 - int(st.get('penalty', 0)) + int(st.get('bonus', 0))))
    return int(score), st

def _grade_mark_order(request):
    """
    تفعيل بونص "اختيار بالترتيب" مرة واحدة (بدون إجبار على الترتيب).
    """
    st = _grade_state(request)
    if not st.get('order_set'):
        st['order_set'] = True
        request.session['pages_order'] = True
        # سجّل الحدث كبونص
        _grade_push(request, "اختيار بالترتيب (Bonus)", +PAGES_BONUS_ORDER)
    # أعد الدرجة الحالية (والحالة لو احتجتها)
    return _grade_get(request)


def _current_question_and_flow(request):
    """
    يرجّع السؤال الجاري (لو موجود في الفلو) + كائن flow كما هو.
    - يعتمد على: request.session['questions'] (قائمة أسئلة)
    - و: request.session['pages_flow'] (قاموس به q_index/current/target_total ...)
    """
    qs = request.session.get('questions') or []
    flow = request.session.get('pages_flow') or {}
    q_index = flow.get('q_index')
    if q_index is None or not (0 <= q_index < len(qs)):
        return None, flow
    return qs[q_index], flow

def _feedback(kind: str, text: str):
    """كائن بسيط للواجهة (success|warning|error|info)."""
    return {"kind": kind, "level": kind, "text": text, "message": text}


def _allowed_juz_numbers_for_scope(request):
    """
    يرجّع قائمة أرقام الأجزاء المسموحة طبقًا لنطاق الاختبار + وجود صفحات فعلًا.
    يعتمد على selected_quarters / selected_juz من السيشن.
    """
    sel_quarters = request.session.get('selected_quarters') or []
    sel_juz = request.session.get('selected_juz') or []

    # أرباع لديها صفحات فعلاً (أي آية فيها page__isnull=False)
    quarters_with_pages = Quarter.objects.filter(
        id=OuterRef('id'),
        ayah__page__isnull=False
    )

    qs = Quarter.objects.all().annotate(
        has_pages=Exists(quarters_with_pages)
    ).filter(has_pages=True)

    if sel_quarters:
        qs = qs.filter(id__in=sel_quarters)
    elif sel_juz:
        try:
            sel_juz = [int(j) for j in sel_juz]
        except Exception:
            sel_juz = []
        if sel_juz:
            qs = qs.filter(juz__number__in=sel_juz)

    allowed = sorted(set(qs.values_list('juz__number', flat=True)))

    # Fallback لو فاضيين: أي جزء فيه صفحات
    if not allowed:
        qs_any = Quarter.objects.annotate(
            has_pages=Exists(Quarter.objects.filter(
                id=OuterRef('id'), ayah__page__isnull=False
            ))
        ).filter(has_pages=True)
        allowed = sorted(set(qs_any.values_list('juz__number', flat=True)))

    return allowed

def _ctx_common(request, extra=None, feedback=None, delta=None):
    """
    يضيف للكونتكست:
    - score_now: الدرجة الحالية
    - current_phrase: نص العبارة الجارية
    - step_no/target_total/step_label: مرحلة اختيار المواضع
    - feedback: رسالة فورية (success/warning/error/info)
    - delta: +1/-1 لتحديث العدّاد بصريًا (اختياري)
    """
    extra = extra or {}
    q, flow = _current_question_and_flow(request)

    st = request.session.get('pages_grade') or {}
    gauge_score = max(0, min(100, 100 - int(st.get('penalty', 0)) + int(st.get('bonus', 0))))
    extra['score_now'] = int(gauge_score)
    extra['gauge_score'] = int(gauge_score)
    extra['gauge_events'] = list((st.get('events') or []))[:6]
    extra['step_no'] = int((flow or {}).get('current') or 1)
    extra['target_total'] = int((flow or {}).get('target_total') or 0)

    phrase = ''
    if q:
        phrase = q.get('phrase_text') or q.get('phrase') or ''
    extra['current_phrase'] = phrase or '—'

    extra['step_label'] = (
        f"الموضع {ar_ordinal(extra['step_no'])}"
        + (f" من {extra['target_total']}" if extra['target_total'] else "")
    )

    if feedback:
        extra['feedback'] = feedback
    if delta is not None:
        extra['delta'] = int(delta)

    return extra


# ------------------------------------------------------------------
# أدوات التطبيع
# ------------------------------------------------------------------
DIAC = re.compile(r'[\u064B-\u0652\u0670\u06DF-\u06ED]')
def norm(txt: str) -> str:
    txt = unicodedata.normalize('NFKD', txt)
    txt = DIAC.sub('', txt)
    txt = txt.replace('إ', 'ا').replace('أ', 'ا').replace('آ', 'ا')
    txt = txt.replace('ة', 'ه').replace('ى', 'ي')
    txt = re.sub(r'[^\w\s]', '', txt)
    return txt

# كلمات لها نهايات/صرفيات شائعة (احتياطي)
WORD_ALIASES = {
    'تكن': r'تكون(?:ن|نَّ)?',
    'قول': r'قول(?:وا)?',
    'تلبسون': r'تلبسون?|تلبسوا(?:ن)?',
}
def flex_regex(word_list):
    parts = []
    for w in word_list:
        key = norm(w)
        pat = WORD_ALIASES.get(key, re.escape(key))
        parts.append(pat)
    return r'\s+'.join(parts)
# ------------------------------------------------------------------

# Configuration
ALLOWED_NUM_QUESTIONS = [5, 10, 15, 20]
COMPLAINT_TYPES = [
    "خطأ في السؤال", "تصميم / واجهة", "اقتراح تحسين",
    "إضافة ميزة", "مشكلة تقنية", "أخرى",
]

def make_options(correct_count: int):
    """اختيارات مرتّبة تصاعديًا بدون تدوير، حول الإجابة الصحيحة."""
    pool = {correct_count}
    for off in (-3, -2, -1, 1, 2, 3, 4, 5):
        v = correct_count + off
        if v >= 1:
            pool.add(v)
        if len(pool) >= 4:
            break
    return sorted(pool)[:4]


def _build_scope_label(selected_juz_ids, selected_quarter_ids):
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

# --------------------------- landing --------------------------- #
def landing(request):
    """صفحة هبوط عامة في الجذر /"""
    # لو المستخدم مسجّل دخوله، حوّله للـ Home
    if request.user.is_authenticated:
        student, _ = Student.objects.get_or_create(
            user=request.user, defaults={'display_name': request.user.username}
        )
        request.session['student_id'] = student.id
        return redirect('core:main_menu')

    # لو مش مسجّل دخوله، اعرض الاندينج عادي
    ctx = {
        'hide_footer': False,
        'show_splash': True,
        'is_logged_in': False,
    }
    return render(request, 'core/landing.html', ctx)



# --------------------------- auth --------------------------- #
def login_view(request):
    # لو المستخدم داخل بالفعل، ودِّيه على الهوم
    if request.user.is_authenticated:
        student, _ = Student.objects.get_or_create(
            user=request.user, defaults={'display_name': request.user.username}
        )
        request.session['student_id'] = student.id
        return redirect('core:main_menu')

    if request.method == 'POST':
        identifier = request.POST.get('username', '').strip()
        password   = request.POST.get('password', '').strip()

        if not identifier or not password:
            messages.error(request, "كل الحقول مطلوبة لتسجيل الدخول.")
            return redirect('core:login')

        # ابحث أولاً بـ display_name ثم username ثم email (بدون حساسية لحالة الأحرف)
        user_obj = None
        stu = Student.objects.select_related('user').filter(display_name__iexact=identifier).first()
        if stu:
            user_obj = stu.user
        else:
            user_obj = User.objects.filter(username__iexact=identifier).first()
            if not user_obj:
                user_obj = User.objects.filter(email__iexact=identifier).first()

        user = None
        if user_obj:
            user = authenticate(request, username=user_obj.username, password=password)

        if user is None:
            messages.error(request, "اسم الدخول/البريد أو كلمة المرور غير صحيحة.")
            return redirect('core:login')

        login(request, user)
        student, _ = Student.objects.get_or_create(user=user, defaults={'display_name': user.username})
        request.session['student_id'] = student.id
        return redirect('core:main_menu')

    return render(request, 'core/login.html', {'hide_footer': False})


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('core:main_menu')

    if request.method == 'POST':
        student_name = request.POST.get('student_name','').strip()
        password = request.POST.get('password','').strip()

        if not student_name:
            messages.error(request,"اسم الطالب مطلوب للتسجيل.")
            return redirect('core:signup')
        if not password:
            messages.error(request,"كلمة المرور مطلوبة.")
            return redirect('core:signup')

        # تحقق المتطلبات عبر Validators الرسمية
        username = student_name.lower().replace(' ','_')
        try:
            tmp_user = User(username=username, email="")
            validate_password(password, user=tmp_user)
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
            return redirect('core:signup')

        # امنع تكرار اسم الطالب (display_name)
        if Student.objects.filter(display_name__iexact=student_name).exists():
            messages.error(request, "اسم الطالب مستخدم بالفعل. لو ده حسابك جرّب تسجيل الدخول، أو اختر اسمًا مميزًا.")
            return redirect('core:signup')

        if User.objects.filter(username=username).exists():
            messages.error(request,"اسم المستخدم موجود بالفعل. جرّب تعديل الاسم قليلًا.")
            return redirect('core:signup')

        try:
            user = User.objects.create_user(username=username)
            user.set_password(password)
            user.save()
        except IntegrityError:
            messages.error(request,"حصل خطأ في إنشاء الحساب، جرب اسم آخر.")
            return redirect('core:signup')

        student = Student.objects.create(user=user, display_name=student_name)
        login(request,user)
        request.session['student_id'] = student.id
        return redirect('core:main_menu')

    return render(request,'core/signup.html', {'hide_footer': False})


@login_required
def logout_view(request):
    logout(request)
    messages.success(request,"تم تسجيل الخروج.")
    return redirect('core:login')

@login_required
def main_menu(request):
    sid = request.session.get('student_id')
    if not sid:
        student, _ = Student.objects.get_or_create(
            user=request.user, defaults={'display_name': request.user.username}
        )
        request.session['student_id'] = student.id
    student = get_object_or_404(Student, id=request.session['student_id'])

    stats = _user_stats(student)
    # ترتيب المستخدم (لو سبق له الامتحان)
    lb_all = _leaderboard()
    my_rank = next((r['rank'] for r in lb_all if r['student_id'] == student.id), None)

    return render(request,'core/main_menu.html',{
        'student': student,
        'stats': stats,
        'my_rank': my_rank,
        'show_splash': True,
        'hide_footer': False,
    })


# === حساب نقاط السكوربورد (احتفظنا بيها لو حبيت تستخدمها لاحقًا) ===
def _score_formula(exams, correct, wrong, unanswered):
    # أساس عادل + مكافأة دقة + مكافأة حجم نشاط (سقف 30 امتحان)
    base = correct - 0.6 * wrong - 0.2 * unanswered
    acc = (correct / (correct + wrong)) if (correct + wrong) else 0.0
    volume_bonus = min(exams, 30) * 2
    return round(max(0, base + 40 * acc + volume_bonus), 2)


@login_required
def leaderboard(request):
    student = get_object_or_404(Student, user=request.user)
    rows = _leaderboard()
    my_rank = next((r['rank'] for r in rows if r['student_id'] == student.id), None)
    return render(request, 'core/leaderboard.html', {
        'rows'      : rows,
        'student'   : student,
        'my_rank'   : my_rank,
        'hide_footer': False,
    })


def _leaderboard():
    """
    لوح منافسة عادل:
    - accuracy (الدقة) لها وزن أساسي.
    - correct (إجمالي الصح) له وزن بحساب لوجاريتمي (علشان يقلّل أثر التفرعات الكبيرة).
    - exams (عدد الامتحانات المكتملة) له وزن برضه لوجاريتمي.
    score = 600*accuracy + 300*log10(1+correct) + 100*log10(1+exams)
    """
    # كل الجلسات المكتملة
    sess = (TestSession.objects
            .filter(completed=True)
            .values('student')
            .annotate(exams=Count('id'),
                      total_q=Sum('num_questions')))

    # إجابات الأسئلة المربوطة بجلسات مكتملة
    ans = (TestQuestion.objects
           .filter(session__completed=True)
           .values('session__student')
           .annotate(
               answered=Count('id'),
               correct=Count('id', filter=Q(is_correct=True)),
               wrong=Count('id', filter=Q(is_correct=False)),
           ))

    by_student = {}
    for r in sess:
        sid = r['student']
        by_student[sid] = {
            'student_id': sid,
            'exams': r.get('exams', 0) or 0,
            'total_q': r.get('total_q', 0) or 0,
            'answered': 0,
            'correct': 0,
            'wrong': 0,
        }
    for r in ans:
        sid = r['session__student']
        row = by_student.setdefault(sid, {
            'student_id': sid, 'exams': 0, 'total_q': 0,
            'answered': 0, 'correct': 0, 'wrong': 0
        })
        row['answered'] = (row['answered'] or 0) + (r.get('answered', 0) or 0)
        row['correct']  = (row['correct']  or 0) + (r.get('correct', 0) or 0)
        row['wrong']    = (row['wrong']    or 0) + (r.get('wrong', 0) or 0)

    if not by_student:
        return []

    sids = list(by_student.keys())
    students = (Student.objects
                .select_related('user')
                .filter(id__in=sids))
    stu_map = {s.id: s for s in students}

    rows = []
    for sid, r in by_student.items():
        s = stu_map.get(sid)
        if not s:
            continue
        exams = r['exams'] or 0
        if exams <= 0:
            # ما يدخلش اللوحة إلا اللي عنده امتحان مكتمل على الأقل
            continue
        correct = r['correct'] or 0
        wrong   = r['wrong'] or 0
        answered = r['answered'] or 0
        total_q = r['total_q'] or 0
        unanswered = max(0, total_q - answered)

        # الدقة تحسب غير مُجاب أيضًا
        denom = max(1, correct + wrong + unanswered)
        accuracy = correct / denom

        # خصم بسيط مقابل غير المُجاب + منع السكور السالب
        score = (600.0 * accuracy) \
                + (300.0 * math.log10(1 + correct)) \
                + (100.0 * math.log10(1 + exams)) \
                - (10.0 * unanswered)
        score = int(round(max(0, score)))


        rows.append({
            'student_id': sid,
            'display_name': s.display_name or s.user.username,
            'avatar': s.avatar.url if getattr(s, 'avatar', None) else '',
            'exams': exams,
            'correct': correct,
            'wrong': wrong,
            'unanswered': unanswered,
            'accuracy': accuracy,
            'accuracy_pct': round(accuracy*100, 2),
            'score': score,
        })

    # الترتيب والتساوي
    rows.sort(key=lambda x: (-x['score'], -x['accuracy'], -x['correct'], x['display_name']))
    last_score = None
    rank = 0
    for i, r in enumerate(rows, start=1):
        if r['score'] != last_score:
            rank = i
            last_score = r['score']
        r['rank'] = rank

    return rows


# ---------------------- complaint ------------------------ #
@login_required
def complaint(request):
    sid=request.session.get('student_id')
    if not sid:
        messages.warning(request,"الرجاء تسجيل الدخول أولاً."); return redirect('core:login')
    student=get_object_or_404(Student,id=sid)
    if request.method == 'POST':
        cats=request.POST.getlist('category'); txt=request.POST.get('text','').strip()
        if not txt and not cats:
            messages.error(request,"لا يمكن إرسال شكوى فارغة.")
        else:
            prefix=f"[{', '.join(cats)}] " if cats else ''
            Complaint.objects.create(student=student, text=prefix+txt if txt else prefix)
            messages.success(request,"تم إرسال الشكوى/الاقتراح بنجاح.")
            return redirect('core:main_menu')
    return render(request,'core/complaint.html',{'student':student,'types':COMPLAINT_TYPES, 'hide_footer': False})



# -----------------------------------------------------
# 1) كتالوج الاختبارات: النوعين يمرّوا على test_selection
# -----------------------------------------------------
def test_catalog(request):
    tests = [
        {
            "key": "similar_count",
            "title": " عدد مواضع المتشابهات",
            "desc": "يعرض عبارة ويطلب عدد مواضعها الصحيحة في نطاقك.",
            "available": True,
            "url": reverse("core:test_selection") + "?type=similar_count",
        },
        {
            "key": "similar_on_pages",
            "title": "مواضع المتشابهات في الصفحات",
            "desc": "اختيار النطاق ثم تحديد الصفحات والمواضع لكل سؤال.",
            "available": True,
            "url": reverse("core:test_selection") + "?type=similar_on_pages",
        },
        {
            "key": "page_edges_quarters",
            "title": "بداية ونهاية الصفحات مع الأرباع",
            "desc": "استنتاج بدايات/نهايات الآيات بين الصفحات داخل نطاقك.",
            "available": False,
        },
        {
            "key": "order_juz_quarters",
            "title": "اختبار ترتيب الأجزاء والأرباع",
            "desc": "أسئلة لقياس ترتيب الأجزاء والأرباع وتسلسلها.",
            "available": False,
        },
        {
            "key": "semantic_similarities",
            "title": "متشابهات معاني الآيات",
            "desc": "أسئلة على التشابه الدلالي للمعاني.",
            "available": False,
        },
    ]
    return render(request, "core/test_catalog.html", {
        "tests": tests,
        "hide_footer": False,
    })


# -----------------------------------------------------
# 2) شاشة اختيار النطاق (مُوحَّدة للاختبارين)
# -----------------------------------------------------
@login_required
def test_selection(request):
    sid = request.session.get('student_id')
    if not sid:
        messages.warning(request, "الرجاء إدخال اسمك أولاً.")
        return redirect('core:login')
    student = get_object_or_404(Student, id=sid)

    # خزّن نوع الاختبار إن جالك من الكتالوج
    test_type_qs = request.GET.get('type')
    if test_type_qs:
        request.session['selected_test_type'] = test_type_qs
    if not request.session.get('selected_test_type'):
        request.session['selected_test_type'] = 'similar_count'

    if request.method == 'POST':
        sel_juz = request.POST.getlist('selected_juz')
        sel_q   = request.POST.getlist('selected_quarters')
        try:
            num_q = int(request.POST.get('num_questions', 5))
        except ValueError:
            num_q = 5
        if num_q not in [5,10,15,20]:
            num_q = 5

        difficulty = request.POST.get('difficulty', 'mixed')  # لو صفحات مش هنستخدمها لاحقًا

        sel_juz = [int(j) for j in sel_juz if str(j).isdigit()]
        sel_q   = [int(q) for q in sel_q if str(q).isdigit()]
        if not sel_juz and not sel_q:
            messages.error(request, "لازم تختار جزء أو رُبع.")
            return redirect('core:test_selection')

        request.session.update({
            'selected_juz': sel_juz,
            'selected_quarters': sel_q,
            'num_questions': num_q,
            'difficulty': difficulty,
            'test_index': 0,
            'score': 0,
        })
        request.session.pop('scope_label', None)
        return redirect('core:start_test')

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
        'num_questions_options': [5,10,15,20],
        'show_splash': True,
        'hide_footer': False,
        'selected_test_type': request.session.get('selected_test_type', 'similar_count'),
    })


# -----------------------------------------------------
# 3) بدء الاختبار: اختيار الأسئلة ثم التفريع حسب النوع
# -----------------------------------------------------
@login_required
def start_test(request):
    sid = request.session.get('student_id')
    if not sid:
        messages.warning(request, "الرجاء إدخال اسمك أولاً.")
        return redirect('core:login')
    student = get_object_or_404(Student, id=sid)

    juz_ids = request.session.get('selected_juz', [])
    q_ids   = request.session.get('selected_quarters', [])
    desired = int(request.session.get('num_questions', 5))
    difficulty = request.session.get('difficulty','mixed')

    # آيات النطاق
    if q_ids:
        ayat_qs = Ayah.objects.filter(quarter_id__in=q_ids)
    elif juz_ids:
        ayat_qs = Ayah.objects.filter(quarter__juz__number__in=juz_ids)
    else:
        messages.error(request, "مفيش نطاق محدد.")
        return redirect('core:test_selection')

    if not ayat_qs.exists():
        messages.error(request, "النطاق لا يحتوى آيات.")
        return redirect('core:test_selection')

    ayat_ids = list(ayat_qs.values_list('id', flat=True))

    # احصاءات التكرار للنطاق
    MAX_OCC_SCOPE = 60
    stats = (PhraseOccurrence.objects
                .filter(ayah_id__in=ayat_ids)
                .values('phrase_id')
                .annotate(freq=Count('id'))
                .filter(freq__gte=2, freq__lte=MAX_OCC_SCOPE))
    if not stats:
        messages.error(request, "مافيش عبارات متشابهة كافية فى النطاق.")
        return redirect('core:test_selection')

    phrase_ids = [s['phrase_id'] for s in stats]
    freq_map = {s['phrase_id']: s['freq'] for s in stats}

    # occurrences per phrase
    occ_rows = (PhraseOccurrence.objects
                .filter(ayah_id__in=ayat_ids, phrase_id__in=phrase_ids)
                .values('phrase_id', 'ayah_id'))

    occ_by_phrase = {}
    for r in occ_rows:
        occ_by_phrase.setdefault(r['phrase_id'], set()).add(r['ayah_id'])

    phrases = {p.id: p for p in Phrase.objects.filter(id__in=phrase_ids)}

    # إزالة العبارات الفرعية
    sorted_pids = sorted(
        phrase_ids,
        key=lambda pid: (-phrases[pid].length_words, -freq_map[pid], phrases[pid].text)
    )
    kept, kept_sets = [], []
    for pid in sorted_pids:
        aset = occ_by_phrase[pid]
        if any(aset.issubset(S) for S in kept_sets):
            continue
        kept.append(pid); kept_sets.append(aset)

    # buckets (نفس قواعد القديم لضمان جودة الانتقاء)
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
        ph = phrases[pid]; freq = freq_map[pid]
        b = bucket(ph.length_words, freq)
        if b == 'other': continue
        ayahs = (Ayah.objects
                 .filter(id__in=occ_by_phrase[pid])
                 .select_related('quarter__juz')
                 .order_by('surah', 'number'))
        literal = [{
            'surah': a.surah, 'number': a.number,
            'juz_number': a.quarter.juz.number if a.quarter else None,
            'quarter_label': a.quarter.label if a.quarter else None,
            'text': a.text,
        } for a in ayahs]
        candidates.append({
            'phrase_id': pid,
            'phrase_text': ph.text,
            'correct_count': freq,
            'occurrence_ayah_ids': list(occ_by_phrase[pid]),
            'literal_ayahs': literal,
            'bucket': b,
            'score': freq * math.log(1 + ph.length_words),
        })

    if not candidates:
        messages.error(request, "بعد تطبيق مستوى الصعوبة مابقاش فيه أسئلة مناسبة.")
        return redirect('core:test_selection')

    # اختيار نهائي
    if difficulty == 'mixed':
        E = [c for c in candidates if c['bucket']=='easy']
        M = [c for c in candidates if c['bucket']=='medium']
        H = [c for c in candidates if c['bucket']=='hard']
        random.shuffle(E); random.shuffle(M); random.shuffle(H)

        ne = max(0, round(desired * 0.40))
        nm = max(0, round(desired * 0.45))
        nh = max(0, desired - ne - nm)

        take = E[:ne] + M[:nm] + H[:nh]
        for pool in [M[nm:], E[ne:], H[nh:]]:
            if len(take) >= desired: break
            need = desired - len(take)
            take += pool[:need]
        selected = take[:desired]
        random.shuffle(selected)
    else:
        filtered = [c for c in candidates if c['bucket']==difficulty]
        if not filtered:
            messages.error(request, "لا توجد أسئلة مناسبة لهذا المستوى في النطاق.")
            return redirect('core:test_selection')
        filtered.sort(key=lambda x: (-x['score'], x['phrase_text']))
        selected = filtered[:desired]

    # إنشاء جلسة اختبار + أسئلة DB (زي القديم)
    selected_type = request.session.get('selected_test_type', 'similar_count')
    session_db = TestSession.objects.create(
        student=student,
        test_type=selected_type,
        num_questions=len(selected),
        difficulty=difficulty,
        completed=False,
    )
    if juz_ids:
        session_db.juzs.add(*Juz.objects.filter(number__in=juz_ids))
    if q_ids:
        session_db.quarters.add(*Quarter.objects.filter(id__in=q_ids))
    request.session['db_session_id'] = session_db.id

    db_qids = []
    for _ in selected:
        tq = TestQuestion.objects.create(session=session_db)
        db_qids.append(tq.id)
    request.session['db_question_ids'] = db_qids

    request.session['scope_label'] = _build_scope_label(juz_ids, q_ids)
    request.session['questions'] = [{
        'phrase_id': c['phrase_id'],
        'phrase_text': c['phrase_text'],
        'correct_count': c['correct_count'],
        'occurrence_ayah_ids': c['occurrence_ayah_ids'],
        'literal_ayahs': c['literal_ayahs'],
        'given_answer': None,
    } for c in selected]
    request.session['test_index'] = 0
    request.session['score'] = 0

    return redirect('core:test_question')




# -------------------- test question ------------------------- #
@login_required
def test_question(request):
    sid = request.session.get('student_id')
    if not sid:
        messages.warning(request, "الرجاء إدخال اسمك أولاً.")
        return redirect('core:login')
    student = get_object_or_404(Student, id=sid)

    idx   = request.session.get('test_index', 0)
    qs    = request.session.get('questions', [])
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
            TestSession.objects.filter(id=db_sid).update(completed=True)

        # نظّف السيشن (بما فيها مفاتيح الـDB)
        for k in ['questions','test_index','score','selected_juz','selected_quarters',
                  'num_questions','scope_label','difficulty','db_session_id','db_question_ids']:
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
        return redirect('core:test_question')

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
            return redirect('core:pages_choose_juz')

        # غير كده: فلو الامتحان الأول كالعادة
        if ans and ans.isdigit() and int(ans) == correct_count:
            request.session['score'] = request.session.get('score', 0) + 1
        request.session['test_index'] = idx + 1
        return redirect('core:test_question')

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
    options = make_options(correct_count)

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

# -------------------- admin complaints ---------------------- #
@user_passes_test(lambda u:u.is_staff)
def admin_complaints(request):
    comps=Complaint.objects.select_related('student__user').order_by('-created_at')
    if request.method=='POST':
        cid=request.POST.get('complaint_id'); action=request.POST.get('action')
        try:
            c=Complaint.objects.get(id=cid)
            if action=='toggle':
                c.resolved=not c.resolved; c.save()
                messages.success(request,f"تم تحديث حالة الشكوى #{cid}.")
        except Complaint.DoesNotExist:
            messages.error(request,"الشكوى غير موجودة.")
    return render(request,'core/complaint_admin.html',{'complaints':comps, 'hide_footer': False})

# -------------------- report question (زر الإبلاغ) --------- #
from django.http import JsonResponse

@login_required
@require_POST
def report_question(request):
    sid = request.session.get('student_id')
    student = get_object_or_404(Student, id=sid)

    text = (request.POST.get('text','') or '').strip() or '(بدون وصف)'
    phrase = (request.POST.get('phrase','') or '').strip()
    q_no = request.POST.get('question_number','?')
    given = request.POST.get('given','—')
    correct = request.POST.get('correct','—')
    src = request.POST.get('from','test')

    body = (
        f"[إبلاغ سؤال — المصدر: {src}] "
        f"سؤال رقم: {q_no} | العبارة: \"{phrase}\" | إجابة الطالب: {given} | الصحيحة: {correct}\n"
        f"وصف المشكلة: {text}"
    )
    Complaint.objects.create(student=student, text=body)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({"ok": True, "message": "تم إرسال الإبلاغ. شكراً لك."})

    return render(request, 'core/report_done.html', {'hide_footer': True})

@login_required
def account_settings(request):
    student = get_object_or_404(Student, user=request.user)
    prof_form = AccountForm(initial={
        'display_name': student.display_name,
        'email': request.user.email,
    })
    pass_form = PasswordChangeTightForm(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            prof_form = AccountForm(request.POST, request.FILES)
            if prof_form.is_valid():
                request.user.email = prof_form.cleaned_data.get('email', '') or ''
                request.user.save()
                student.display_name = prof_form.cleaned_data['display_name']
                avatar_file = prof_form.cleaned_data.get('avatar')
                if avatar_file:
                    student.avatar = avatar_file
                if request.POST.get('remove_avatar') == '1' and student.avatar:
                    student.avatar.delete(save=False)
                    student.avatar = None
                student.save()
                messages.success(request, "تم تحديث بيانات الحساب.")
                return redirect('core:account_settings')
        elif action == 'change_password':
            pass_form = PasswordChangeTightForm(user=request.user, data=request.POST)
            if pass_form.is_valid():
                user = pass_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "تم تحديث كلمة المرور.")
                return redirect('core:account_settings')

    return render(request,'core/account_settings.html',{
        'student': student,
        'profile_form': prof_form,
        'password_form': pass_form,
        'hide_footer': False,
    })

def _user_stats(student: Student):
    """احسب إحصائيات المستخدم من الجلسات والأسئلة المخزنة (بدقة)."""
    # نستخدم الأسئلة الفعلية المسجّلة
    qs = TestQuestion.objects.filter(session__student=student)
    total_qs = qs.count()
    correct = qs.filter(is_correct=True).count()
    # الغلط المُجاب: is_correct=False لكن فيه student_response
    wrong   = qs.filter(is_correct=False).exclude(student_response='').exclude(student_response__isnull=True).count()
    answered = qs.exclude(student_response='').exclude(student_response__isnull=True).count()
    unanswered = max(0, total_qs - answered)

    # عدد الامتحانات المكتملة
    exams = TestSession.objects.filter(student=student, completed=True).count()

    return {
        'exams': exams,
        'correct': correct,
        'wrong': wrong,
        'unanswered': unanswered,
    }

@login_required
def stats(request):
    student = get_object_or_404(Student, user=request.user)
    data = _user_stats(student)
    return render(request, 'core/stats.html', {
        'student': student,
        'stats': data,
        'hide_footer': False,
    })


@login_required
def quarter_pages_api(request, qid: int):
    qs = (Ayah.objects
          .filter(quarter_id=qid, page__isnull=False)
          .values_list('page__number', flat=True)
          .distinct())
    pages = sorted(set(p for p in qs if p is not None))
    pmin = pages[0] if pages else None
    items = []
    for p in pages:
        items.append({
            "page_number": p,
            "index_in_quarter": (p - pmin + 1) if pmin else None
        })
    return JsonResponse({"pages": items})

@login_required
def page_ayat_api(request, pno: int):
    ay = (Ayah.objects
          .filter(page__number=pno)
          .order_by('surah','number')
          .values('id','surah','number','text','quarter_id'))
    data = [{
        "id": a["id"],
        "vk": f"{a['surah']}:{a['number']}",
        "text": a["text"],
        "quarter_id": a["quarter_id"],
    } for a in ay]
    return JsonResponse({"page": pno, "ayat": data})

@login_required
def quarter_pages_view(request, qid: int):
    pg_nums = (Ayah.objects
               .filter(quarter_id=qid, page__isnull=False)
               .values_list('page__number', flat=True))
    pg_nums = sorted(set(pg for pg in pg_nums if pg is not None))
    pages = Page.objects.filter(number__in=pg_nums).order_by('number')
    return render(request, 'core/quarter_pages.html', {
        'qid': qid,
        'pages': pages,
        'hide_footer': True,
    })

def page_svg(request, pno: int):
    candidates = [f"{pno}.svg", f"{pno:02d}.svg", f"{pno:03d}.svg"]
    base = os.path.join(settings.MEDIA_ROOT, 'pages')
    for fname in candidates:
        path = os.path.join(base, fname)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return FileResponse(open(path, 'rb'), content_type='image/svg+xml')
    raise Http404("Page SVG not found")


# =========================
# Similar on pages: steps B/C
# =========================
# === pages_quarter_pick (استبدال الدالة) ===
@login_required
def pages_quarter_pick(request, qid: int):
    sid = request.session.get('student_id')
    student = get_object_or_404(Student, id=sid)

    qobj = get_object_or_404(Quarter, id=qid)
    juz_no_for_q = qobj.juz.number

    question, flow = _current_question_and_flow(request)
    feedback = None
    delta = None

    if question:
        expected = int((request.session.get('pages_flow') or {}).get('current', 1))
        occ_ids = question.get('occurrence_ayah_ids', []) or []
        ay_quarters = list(
            Ayah.objects.filter(id__in=occ_ids)
                .order_by('surah','number')
                .values_list('id','quarter_id')
        )
        idx_to_qid = {i: q for i, (_, q) in enumerate(ay_quarters, start=1)}
        expected_qid = idx_to_qid.get(expected)

        if expected_qid == qid:
            # ✅ الموضع اكتمل عند اختيار الربع الصحيح
            cfg = _pages_cfg_get(request)
            per_pos = cfg['per_pos']  # 100 / عدد المواضع
            score_now, delta = _grade_push(request, f"إتمام موضع {ar_ordinal(expected)}", +per_pos)
            flow = _flow_mark_completed(request)
            feedback = _feedback('success', f"تمام! اخترت الربع الصحيح للموضع {ar_ordinal(expected)}. (+{per_pos}%)")
            # ارجع لاختيار الجزء لبدء الموضع التالي مباشرة
            return redirect('core:pages_choose_juz')

        else:
            picked_index = next((i for i, q in idx_to_qid.items() if q == qid), None)
            if picked_index:
                # الربع يخص موضع آخر
                flow['current'] = picked_index
                request.session['pages_flow'] = flow
                score_now, delta = _grade_push(request, "اختيار ربع يخص موضع آخر", -PENALTY_WRONG_QUARTER_OTHER)
                feedback = _feedback('warning', f"الربع المختار يخص الموضع {ar_ordinal(picked_index)} وليس {ar_ordinal(expected)}. سنكمل على هذا الموضع. {delta}%−")
            else:
                # مفيش أي موضع في هذا الربع → خصم وتعطيل الربع في هذه المرحلة
                score_now, delta = _grade_push(request, "لا يوجد أي موضع في هذا الربع", -PENALTY_EMPTY_QUARTER)
                flow = request.session.get('pages_flow') or {}
                current_step = int((flow or {}).get('current') or 1)
                dis = (flow.setdefault('disabled', {}).setdefault(f"step_{current_step}", {'juz': [], 'q': []}))
                if qid not in dis['q']:
                    dis['q'].append(qid)
                request.session['pages_flow'] = flow

                # أعد عرض قائمة أرباع الجزء نفسه مع تعطيل هذا الربع
                quarters = Quarter.objects.filter(juz__number=juz_no_for_q).order_by('index_in_juz')
                ctx = {
                    'student': student,
                    'juz_no': juz_no_for_q,
                    'quarters': quarters,
                    'hide_footer': True,
                    'disabled_quarters': dis['q'],
                }
                # مرر الجيج/الإحصائيات + التقدّم
                score_now2, st = _grade_get(request)
                ctx.update({
                    'gauge_score': score_now2,
                    'gauge_events': (st.get('events') or [])[:6],
                    'flow_total': flow.get('total'),
                    'flow_current': flow.get('current'),
                    'flow_completed': flow.get('completed', []),
                })
                fb = _feedback('error', f"لا يوجد أي موضع في هذا الربع. {delta}%−")
                return render(request, 'core/pages_choose_quarter.html', _ctx_common(request, ctx, fb, delta))

    # لو وصلنا هنا بدون سؤال/تقييم: اعرض صفحات الربع (fallback قديم)
    pg_nums = (Ayah.objects
               .filter(quarter_id=qid, page__isnull=False)
               .values_list('page__number', flat=True))
    pg_nums = sorted(set(pg for pg in pg_nums if pg is not None))
    pages = Page.objects.filter(number__in=pg_nums).order_by('number')

    ctx = {
        'qid': qid,
        'pages': pages,
        'hide_footer': True,
    }
    return render(request, 'core/quarter_pages.html', _ctx_common(request, ctx, feedback, delta))


@login_required
@require_POST
def api_pages_select_first(request):
    sid = request.session.get('student_id')
    get_object_or_404(Student, id=sid)

    try:
        ayah_id = int(request.POST.get('ayah_id', '0'))
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'ayah_id_invalid'}, status=400)

    if not Ayah.objects.filter(id=ayah_id).exists():
        return JsonResponse({'ok': False, 'error': 'ayah_not_found'}, status=404)

    # خزّن اختيار أول آية لهذا السؤال الجاري
    flow = request.session.get('pages_flow', {}) or {}
    flow['first_ayah_id'] = ayah_id
    request.session['pages_flow'] = flow

    return JsonResponse({'ok': True, 'next': 'pick_page_position'})


@login_required
def pages_quarter_viewer(request, qid: int):
    sid = request.session.get('student_id')
    student = get_object_or_404(Student, id=sid)

    pg_nums = (Ayah.objects
               .filter(quarter_id=qid, page__isnull=False)
               .values_list('page__number', flat=True))
    pages = sorted(set(p for p in pg_nums if p is not None))
    if not pages:
        # بدل الرسالة، نرجّع لاختيار الجزء/الربع بدون توست:
        quarters = Quarter.objects.filter(id=qid).select_related('juz')
        juz_no = quarters[0].juz.number if quarters else None
        if juz_no:
            ctx = {
                'student': student,
                'juz_no': juz_no,
                'quarters': Quarter.objects.filter(juz__number=juz_no).order_by('index_in_juz'),
                'hide_footer': True,
            }
            fb = _feedback('error', "لا توجد صفحات لهذا الربع.")
            return render(request, 'core/pages_choose_quarter.html', _ctx_common(request, ctx, fb, None))
        return redirect('core:pages_choose_juz')

    spreads = []
    i = 0
    while i < len(pages):
        left = pages[i]
        right = pages[i+1] if i+1 < len(pages) else None
        spreads.append((left, right))
        i += 2

    ctx = {
        'qid': qid,
        'spreads': spreads,
        'first_pair': spreads[0],
        'hide_footer': True,
    }
    return render(request, 'core/quarter_viewer.html', _ctx_common(request, ctx))


from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

@login_required
def pages_choose_juz(request):
    # الطالب
    sid = request.session.get('student_id')
    student = get_object_or_404(Student, id=sid)

    # إعدادات وعدّاد التقدم
    cfg = _pages_cfg_get(request)          # {'total': N, 'per_pos': 100/N}
    flow = _flow_get(request)              # {'current':1..N, 'completed':[...], 'total':N}

    # AJAX: تفعيل البونص أو تعيين عدد المواضع بدون تنقّل
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.GET.get('ajax'):
        # تفعيل "بالترتيب" كبونص فقط (لا يجبر المستخدم على ترتيب الاختيار)
        if request.GET.get('order') == '1':
            score_now, _ = _grade_mark_order(request)
            request.session['pages_order'] = True
            ev = {'t': "اختيار بالترتيب (Bonus)", 'd': PAGES_BONUS_ORDER}
            return JsonResponse({
                'ok': True,
                'gauge_score': score_now,
                'event': ev,
                'order_mode': True
            })

        # تعيين عدد المواضع
        if request.GET.get('set_n'):
            try:
                n = int(request.GET.get('set_n'))
            except Exception:
                n = cfg['total']
            cfg, flow = _flow_set_total(request, n)
            ev = {'t': f"تعيين عدد المواضع إلى {cfg['total']}", 'd': 0}
            return JsonResponse({
                'ok': True,
                'flow': flow,
                'cfg': cfg,
                'event': ev
            })

        return JsonResponse({'ok': False}, status=400)

    # الأجزاء المتاحة ضمن النطاق
    allowed_juz_numbers = _allowed_juz_numbers_for_scope(request)

    # جهّز الكونتكست الأساسي
    context = {
        'student': student,
        'juz_numbers': allowed_juz_numbers,
        'had_scope': bool(request.session.get('selected_quarters') or request.session.get('selected_juz')),
        'hide_footer': True,
    }

    # fallback قديم: دعم ?order=1/0 لو اتبعت كرابط (مش AJAX)
    order_param = request.GET.get('order')
    if order_param in ('0', '1'):
        if order_param == '1':
            _grade_mark_order(request)
            request.session['pages_order'] = True
        else:
            request.session['pages_order'] = False

    # سبب عدم وجود أجزاء
    if not allowed_juz_numbers:
        reason = []
        if request.session.get('selected_quarters') or request.session.get('selected_juz'):
            reason.append("النطاق الذي اخترته لا يحتوي على أرباع بها صفحات.")
        else:
            reason.append("لا توجد صفحات مرتبطة بالأرباع حتى الآن.")
        context['no_juz_reason'] = " ".join(reason)

    # اجمع قائمة الأجزاء المقفولة في نفس الموضع (عشان تتعطّل في الواجهة)
    flow_state = request.session.get('pages_flow') or {}
    current_step = int(flow.get('current', 1))
    disabled_step = (flow_state.get('disabled', {}) or {}).get(
        f"step_{current_step}",
        {'juz': [], 'q': []}
    )
    context['disabled_juz'] = disabled_step.get('juz', [])

    # نحسب السكور الحالي ونمرر الإحصائيات + وضع "بالترتيب" + تقدّم المواضع
    score_now, st = _grade_get(request)
    context.update({
        'gauge_score': score_now,
        'gauge_events': (st.get('events') or [])[:6],
        'order_mode': bool(request.session.get('pages_order')),
        'flow_total': flow.get('total'),
        'flow_current': flow.get('current'),
        'flow_completed': flow.get('completed', []),
        'n_options': list(range(1, 11)),   # <<<<< هنا
    })

    return render(request, 'core/pages_choose_juz.html', _ctx_common(request, context))



@login_required
def pages_choose_quarter(request, juz_no: int):
    sid = request.session.get('student_id')
    student = get_object_or_404(Student, id=sid)

    # جهّز التقييم على الموضع المتوقع
    question, flow = _current_question_and_flow(request)
    feedback = None
    delta = None

    # quarters لهذا الجزء
    quarters = Quarter.objects.filter(juz__number=juz_no).order_by('index_in_juz')

    if question:
        expected = int((request.session.get('pages_flow') or {}).get('current', 1))
        occ_ids = question.get('occurrence_ayah_ids', []) or []
        ay_juzs = list(
            Ayah.objects.filter(id__in=occ_ids)
                .order_by('surah','number')
                .values_list('id','quarter__juz__number')
        )
        idx_to_juz = {i: j for i, (_, j) in enumerate(ay_juzs, start=1)}
        expected_juz = idx_to_juz.get(expected)

        if expected_juz is not None:
            if juz_no == expected_juz:
                score_now, delta = _grade_push(request, "إجابة صحيحة", 0)
                feedback = _feedback('success', f"تمام! اخترت الجزء الصحيح للموضع {ar_ordinal(expected)}.")
            else:
                # هل يخص موضعًا آخر؟
                picked_index = next((i for i, j in idx_to_juz.items() if j == juz_no), None)
                if picked_index:
                    flow['current'] = picked_index
                    request.session['pages_flow'] = flow
                    score_now, delta = _grade_push(request, "اختيار جزء يخص موضع آخر", -PENALTY_WRONG_JUZ_OTHER)
                    feedback = _feedback('warning', f"الجزء المختار يخص الموضع {ar_ordinal(picked_index)} وليس {ar_ordinal(expected)}. سنكمل على هذا الموضع. {delta}%−")
                else:
                    # لا يوجد أي موضع في هذا الجزء → خصم وتعطيل هذا الجزء في هذه المرحلة
                    score_now, delta = _grade_push(request, "لا يوجد أي موضع في هذا الجزء", -PENALTY_EMPTY_JUZ)
                    flow = request.session.get('pages_flow') or {}
                    current_step = int((flow or {}).get('current') or 1)
                    dis = (flow.setdefault('disabled', {}).setdefault(f"step_{current_step}", {'juz': [], 'q': []}))
                    if juz_no not in dis['juz']:
                        dis['juz'].append(juz_no)
                    request.session['pages_flow'] = flow
                    feedback = _feedback('error', f"لا يوجد أي موضع في هذا الجزء. {delta}%−")

    # جهّز disabled_quarters لهذا الموضع (لو سبق تعطيل أرباع)
    flow_state = request.session.get('pages_flow') or {}
    current_step = int((flow or {}).get('current', 1))
    disabled_step = (flow_state.get('disabled', {}) or {}).get(
        f"step_{current_step}",
        {'juz': [], 'q': []}
    )

    ctx = {
        'student': student,
        'juz_no': juz_no,
        'quarters': quarters,
        'hide_footer': True,
        'disabled_quarters': disabled_step.get('q', []),
    }

    # مرر الجيج/الإحصائيات + التقدّم
    score_now, st = _grade_get(request)
    ctx.update({
        'gauge_score': score_now,
        'gauge_events': (st.get('events') or [])[:6],
        'flow_total': flow.get('total'),
        'flow_current': flow.get('current'),
        'flow_completed': flow.get('completed', []),
    })

    return render(request, 'core/pages_choose_quarter.html', _ctx_common(request, ctx, feedback, delta))


# ===== Flow / config helpers =====
def _pages_cfg_get(request):
    """Config: total targets (N) and per-position share."""
    cfg = request.session.get('pages_cfg') or {}
    total = int(cfg.get('total') or 3)  # قيمة افتراضية
    per_pos = cfg.get('per_pos')
    if not per_pos:
        per_pos = round(100 / max(1, total), 2)
    cfg['total'] = total
    cfg['per_pos'] = per_pos
    request.session['pages_cfg'] = cfg
    return cfg

def _flow_get(request):
    """current: 1-indexed; completed: list of ints."""
    flow = request.session.get('pages_flow') or {}
    flow.setdefault('current', 1)
    flow.setdefault('completed', [])
    cfg = _pages_cfg_get(request)
    flow['total'] = cfg['total']
    request.session['pages_flow'] = flow
    return flow

def _flow_set_total(request, n:int):
    cfg = _pages_cfg_get(request)
    n = max(1, min(50, int(n)))
    cfg['total'] = n
    cfg['per_pos'] = round(100 / n, 2)
    request.session['pages_cfg'] = cfg
    flow = _flow_get(request)
    flow['total'] = n
    # حافظ على المنجز، و اضبط current لو تعدّى الجديد
    flow['current'] = min(flow.get('current',1), n)
    flow['completed'] = [i for i in flow.get('completed',[]) if 1 <= int(i) <= n]
    request.session['pages_flow'] = flow
    return cfg, flow

def _flow_mark_completed(request):
    flow = _flow_get(request)
    cur = int(flow.get('current',1))
    if cur not in flow['completed']:
        flow['completed'] = list(flow['completed']) + [cur]
    # تقدّم طالما لسه فيه مواضع
    if cur < int(flow.get('total',1)):
        flow['current'] = cur + 1
    request.session['pages_flow'] = flow
    return flow

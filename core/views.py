from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Count, Sum, Q, Exists, OuterRef
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.http import JsonResponse, FileResponse, Http404
from django.conf import settings
import sys
import os, math, random, re, unicodedata
from django.views.decorators.http import require_POST
from .forms import ProfileUpdateForm, PasswordChangeForm
from .models import Student, Complaint, Juz, Quarter, SimilarityGroup, Ayah, Phrase, PhraseOccurrence, TestSession, TestQuestion, Page
from django.contrib.auth import get_user_model
from django.test import TestCase

# UTF-8 safe print for Windows consoles (avoid UnicodeEncodeError)
def print(*args, sep=" ", end="\n", file=None, flush=False):
    try:
        stream = file if file is not None else sys.stdout
        target = getattr(stream, "buffer", None)
        if target is None:
            text = sep.join(str(a) for a in args) + end
            try:
                stream.write(text)
            except Exception:
                pass
            return
        text = sep.join(str(a) for a in args) + end
        target.write(text.encode("utf-8", errors="ignore"))
        if flush and hasattr(stream, "flush"):
            try:
                stream.flush()
            except Exception:
                pass
    except Exception:
        # Silently ignore any console encoding errors during debug prints
        pass



AR_ORD={1:"الأول",2:"الثاني",3:"الثالث",4:"الرابع",5:"الخامس",6:"السادس",7:"السابع",8:"الثامن",9:"التاسع",10:"العاشر"}
def ar_ordinal(n:int)->str: return f"{AR_ORD.get(n,n)}"

PAGES_BONUS_ORDER=15; PENALTY_WRONG_JUZ_OTHER=8; PENALTY_WRONG_QUARTER_OTHER=6; PENALTY_EMPTY_JUZ=5; PENALTY_EMPTY_QUARTER=4; FAIL_THRESHOLD=50

def _grade_state(request):
    st=request.session.get('pages_grade') or {}
    st.setdefault('bonus',0); st.setdefault('penalty',0); st.setdefault('events',[]); st.setdefault('order_set',False)
    request.session['pages_grade']=st; return st

def _grade_push(request,text:str,delta:int):
    st=_grade_state(request)
    if delta>=0: st['bonus']=min(100,int(st.get('bonus',0))+int(delta))
    else: st['penalty']=min(100,int(st.get('penalty',0))+int(-delta))
    st['events'].insert(0,{'t':text,'d':int(delta)}); request.session['pages_grade']=st
    score=max(0,min(100,100-int(st['penalty'])+int(st['bonus']))); return int(score),int(delta)

def _grade_get(request):
    st=_grade_state(request); score=max(0,min(100,100-int(st.get('penalty',0))+int(st.get('bonus',0)))); return int(score),st

def _grade_mark_order(request):
    st=_grade_state(request)
    if not st.get('order_set'):
        st['order_set']=True; request.session['pages_order']=True; _grade_push(request,"اختيار بالترتيب (Bonus)",+PAGES_BONUS_ORDER)
    return _grade_get(request)

def _current_question_and_flow(request):
    qs=request.session.get('questions') or []; flow=request.session.get('pages_flow') or {}; q_index=flow.get('q_index')
    if q_index is None or not (0<=q_index<len(qs)): return None,flow
    return qs[q_index],flow

def _feedback(kind:str,text:str): return {"kind":kind,"level":kind,"text":text,"message":text}

def _allowed_juz_numbers_for_scope(request):
    sel_quarters=request.session.get('selected_quarters') or []; sel_juz=request.session.get('selected_juz') or []
    quarters_with_pages=Quarter.objects.filter(id=OuterRef('id'),ayah__page__isnull=False)
    qs=Quarter.objects.all().annotate(has_pages=Exists(quarters_with_pages)).filter(has_pages=True)
    if sel_quarters: qs=qs.filter(id__in=sel_quarters)
    elif sel_juz:
        try: sel_juz=[int(j) for j in sel_juz]
        except Exception: sel_juz=[]
        if sel_juz: qs=qs.filter(juz__number__in=sel_juz)
    allowed=sorted(set(qs.values_list('juz__number',flat=True)))
    if not allowed:
        qs_any=Quarter.objects.annotate(has_pages=Exists(Quarter.objects.filter(id=OuterRef('id'),ayah__page__isnull=False))).filter(has_pages=True)
        allowed=sorted(set(qs_any.values_list('juz__number',flat=True)))
    return allowed

def _ctx_common(request, extra=None, feedback=None, delta=None):
    extra = extra or {}
    q, _ = _current_question_and_flow(request)
    score_now, st = _grade_get(request)

    gauge_score = max(0, min(100, int(score_now)))
    extra['score_now'] = gauge_score
    extra['gauge_score'] = gauge_score
    extra['gauge_events'] = list(st.get('events') or [])[:6]

    flow = _current_flow(request)
    step_no = int(flow.get('current') or 1)
    total = int(flow.get('total') or 0)
    progress_pct = 0 if total == 0 else int(round((step_no - 1) * 100 / total))
    extra['step_no'] = step_no
    extra['target_total'] = total
    extra['progress_pct'] = progress_pct

    phrase = ''
    if q: phrase = q.get('phrase_text') or q.get('phrase') or ''
    extra['current_phrase'] = phrase or '—'
    extra['step_label'] = f"الموضع {ar_ordinal(step_no)}" + (f" من {total}" if total else "")

    # ← العلم اللي يتحكم بظهور الدائرة في الـlayout
    extra['show_pages_progress'] = (request.session.get('selected_test_type') == 'similar_on_pages')

    if feedback: extra['feedback'] = feedback
    if delta is not None: extra['delta'] = int(delta)
    return extra




DIAC=re.compile(r'[\u064B-\u0652\u0670\u06DF-\u06ED]')
def norm(txt:str)->str:
    txt=unicodedata.normalize('NFKD',txt)
    # حافظ على الألف الخنجرية بتحويلها إلى ألف عادية قبل إزالة التشكيل
    # U+0670 ARABIC LETTER SUPERSCRIPT ALEF (dagger alef)
    txt=txt.replace('\u0670','ا')
    txt=DIAC.sub('',txt)
    txt=txt.replace('إ','ا').replace('أ','ا').replace('آ','ا'); txt=txt.replace('ة','ه').replace('ى','ي')
    txt=re.sub(r'[^\w\s]','',txt); return txt

WORD_ALIASES={'تكن':r'تكون(?:ن|نَّ)?','قول':r'قول(?:وا)?','تلبسون':r'تلبسون?|تلبسوا(?:ن)?'}
def flex_regex(word_list):
    parts=[];
    for w in word_list:
        key=norm(w); parts.append(WORD_ALIASES.get(key,re.escape(key)))
    return r'\s+'.join(parts)

ALLOWED_NUM_QUESTIONS=[5,10,15,20]
COMPLAINT_TYPES=["خطأ في السؤال","تصميم / واجهة","اقتراح تحسين","إضافة ميزة","مشكلة تقنية","أخرى"]

def make_options(correct_count:int):
    pool={correct_count}
    for off in(-3,-2,-1,1,2,3,4,5):
        v=correct_count+off
        if v>=1: pool.add(v)
        if len(pool)>=4: break
    return sorted(pool)[:4]

def _build_scope_label(selected_juz_ids,selected_quarter_ids):
    if selected_quarter_ids:
        quarters=Quarter.objects.filter(id__in=selected_quarter_ids).select_related('juz'); by_juz={}
        for q in quarters: by_juz.setdefault(q.juz.number,[]).append(q)
        parts=[]
        for j in sorted(by_juz):
            qs=by_juz[j]
            if len(qs)==8: parts.append(f"الجزء {j}")
            else:
                idx=', '.join(f"الربع {q.index_in_juz}" for q in sorted(qs,key=lambda x:x.index_in_juz))
                parts.append(f"الجزء {j} - {idx}")
        return "اختبار على: " + "؛ ".join(parts)
    elif selected_juz_ids:
        lbl='؛ '.join(f"الجزء {j}" for j in sorted(selected_juz_ids)); return f"اختبار على: {lbl}"
    return "اختبار على: نطاق غير محدد"

 

 

 

 

 

def _score_formula(exams,correct,wrong,unanswered):
    base=correct-0.6*wrong-0.2*unanswered; acc=(correct/(correct+wrong)) if (correct+wrong) else 0.0; volume_bonus=min(exams,30)*2
    return round(max(0,base+40*acc+volume_bonus),2)

# Leaderboard and student_profile moved to stats_app

def _debug_leaderboard_data():
    """
    دالة تشخيص لفحص بيانات الليدر بورد
    """
    try:
        # فحص جلسات الاختبار
        total_sessions = TestSession.objects.count()
        completed_sessions = TestSession.objects.filter(completed=True).count()
        incomplete_sessions = TestSession.objects.filter(completed=False).count()
        
        # فحص الأسئلة
        total_questions = TestQuestion.objects.count()
        answered_questions = TestQuestion.objects.exclude(student_response='').exclude(student_response__isnull=True).count()
        correct_questions = TestQuestion.objects.filter(is_correct=True).count()
        wrong_questions = TestQuestion.objects.filter(is_correct=False).count()
        
        # فحص الأسئلة من الجلسات المكتملة فقط
        completed_session_questions = TestQuestion.objects.filter(session__completed=True).count()
        completed_session_answered = TestQuestion.objects.filter(
            session__completed=True
        ).exclude(student_response='').exclude(student_response__isnull=True).count()
        completed_session_correct = TestQuestion.objects.filter(
            session__completed=True, is_correct=True
        ).exclude(student_response='').exclude(student_response__isnull=True).count()
        completed_session_wrong = TestQuestion.objects.filter(
            session__completed=True, is_correct=False
        ).exclude(student_response='').exclude(student_response__isnull=True).count()
        
        # فحص الطلاب
        total_students = Student.objects.count()
        students_with_sessions = TestSession.objects.values('student').distinct().count()
        students_with_completed_sessions = TestSession.objects.filter(completed=True).values('student').distinct().count()
        
        debug_info = {
            'total_sessions': total_sessions,
            'completed_sessions': completed_sessions,
            'incomplete_sessions': incomplete_sessions,
            'total_questions': total_questions,
            'answered_questions': answered_questions,
            'correct_questions': correct_questions,
            'wrong_questions': wrong_questions,
            'completed_session_questions': completed_session_questions,
            'completed_session_answered': completed_session_answered,
            'completed_session_correct': completed_session_correct,
            'completed_session_wrong': completed_session_wrong,
            'total_students': total_students,
            'students_with_sessions': students_with_sessions,
            'students_with_completed_sessions': students_with_completed_sessions,
        }
        
        print("=== معلومات تشخيص الليدر بورد ===")
        for key, value in debug_info.items():
            print(f"{key}: {value}")
        print("=================================")
        
        return debug_info
        
    except Exception as e:
        print(f"خطأ في التشخيص: {e}")
        return {}

def _leaderboard():
    """
    دالة حساب الليدر بورد - تحسب إحصائيات الطلاب وترتبهم
    """
    try:
        # تشخيص البيانات أولاً
        debug_info = _debug_leaderboard_data()
        
        # تشخيص إضافي للطلاب الفرديين
        print("\n=== تشخيص الطلاب الفرديين ===")
        for student in Student.objects.all():
            sessions = TestSession.objects.filter(student=student, completed=True)
            questions = TestQuestion.objects.filter(session__in=sessions)
            answered_questions = questions.exclude(student_response='').exclude(student_response__isnull=True)
            correct_questions = answered_questions.filter(is_correct=True)
            wrong_questions = answered_questions.filter(is_correct=False)
            
            print(f"طالب {student.display_name} (ID: {student.id}):")
            print(f"  - جلسات مكتملة: {sessions.count()}")
            print(f"  - أسئلة إجمالي: {questions.count()}")
            print(f"  - أسئلة مجاب عليها: {answered_questions.count()}")
            print(f"  - أسئلة صحيحة: {correct_questions.count()}")
            print(f"  - أسئلة خاطئة: {wrong_questions.count()}")
        print("================================\n")
        
        # الحصول على جميع جلسات الاختبار المكتملة
        # نستخدم distinct=True لتجنب تكرار العد
        sess = TestSession.objects.filter(completed=True).values('student').annotate(
            exams=Count('id', distinct=True),
            total_q=Sum('num_questions')
        )
        
        print(f"عدد الطلاب الذين لديهم جلسات مكتملة: {len(sess)}")
        
        # الحصول على جميع الأسئلة المجاب عليها من الجلسات المكتملة
        # نستخدم distinct=True لتجنب تكرار العد
        # نأخذ فقط الأسئلة التي لها إجابة فعلية
        ans = TestQuestion.objects.filter(
            session__completed=True
        ).exclude(
            student_response=''
        ).exclude(
            student_response__isnull=True
        ).values('session__student').annotate(
            answered=Count('id', distinct=True),
            correct=Count('id', filter=Q(is_correct=True), distinct=True),
            wrong=Count('id', filter=Q(is_correct=False), distinct=True)
        )
        
        print(f"عدد الطلاب الذين لديهم أسئلة مجاب عليها: {len(ans)}")
        
        by_student = {}
        
        # تهيئة البيانات لكل طالب
        for r in sess:
            sid = r['student']
            exams_count = r.get('exams', 0) or 0
            total_questions = r.get('total_q', 0) or 0
            
            # تأكد من أن القيم صحيحة
            if exams_count < 0:
                exams_count = 0
            if total_questions < 0:
                total_questions = 0
            
            print(f"طالب {sid}: امتحانات={exams_count}, أسئلة={total_questions}")
                
            by_student[sid] = {
                'student_id': sid,
                'exams': exams_count,
                'total_q': total_questions,
                'answered': 0,
                'correct': 0,
                'wrong': 0
            }
        
        # إضافة بيانات الإجابات
        for r in ans:
            sid = r['session__student']
            row = by_student.setdefault(sid, {
                'student_id': sid,
                'exams': 0,
                'total_q': 0,
                'answered': 0,
                'correct': 0,
                'wrong': 0
            })
            
            answered_count = r.get('answered', 0) or 0
            correct_count = r.get('correct', 0) or 0
            wrong_count = r.get('wrong', 0) or 0
            
            # تأكد من أن القيم صحيحة
            if answered_count < 0:
                answered_count = 0
            if correct_count < 0:
                correct_count = 0
            if wrong_count < 0:
                wrong_count = 0
            
            print(f"طالب {sid}: إجابات={answered_count}, صحيح={correct_count}, خطأ={wrong_count}")
                
            row['answered'] = (row['answered'] or 0) + answered_count
            row['correct'] = (row['correct'] or 0) + correct_count
            row['wrong'] = (row['wrong'] or 0) + wrong_count
        
        if not by_student:
            return []
        
        # الحصول على بيانات الطلاب
        sids = list(by_student.keys())
        students = Student.objects.select_related('user').filter(id__in=sids)
        stu_map = {s.id: s for s in students}
        
        rows = []
        for sid, r in by_student.items():
            s = stu_map.get(sid)
            if not s:
                continue
                
            exams = r['exams'] or 0
            # إزالة هذا الشرط للسماح بعرض جميع الطلاب حتى لو كان لديهم 0 امتحانات
            # if exams <= 0:
            #     continue
                
            correct = r['correct'] or 0
            wrong = r['wrong'] or 0
            answered = r['answered'] or 0
            total_q = r['total_q'] or 0
            unanswered = max(0, total_q - answered)
            
            print(f"إضافة طالب {s.display_name}: امتحانات={exams}, صحيح={correct}, خطأ={wrong}, إجابات={answered}")
            
            # حساب الدقة - فقط من الأسئلة المجاب عليها
            answered_questions = correct + wrong
            if answered_questions > 0:
                accuracy = correct / answered_questions
            else:
                accuracy = None
            
            # حساب النقاط
            if accuracy is not None:
                score = (800.0 * accuracy) + (200.0 * math.log10(1 + correct)) + (100.0 * math.log10(1 + exams)) - (5.0 * unanswered)
                score = int(round(max(0, score)))
            else:
                score = 0
            
            # استخراج الاسم الأول فقط
            full_name = s.display_name or s.user.username
            first_name = full_name.split()[0] if full_name else s.user.username
            
            rows.append({
                'student_id': sid,
                'display_name': first_name,
                'avatar': s.avatar.url if getattr(s, 'avatar', None) else '',
                'skin': s.skin or 'default',
                'exams': exams,
                'correct': correct,
                'wrong': wrong,
                'unanswered': unanswered,
                'accuracy': accuracy,
                'accuracy_pct': (round(accuracy * 100, 2) if accuracy is not None else None),
                'score': score
            })
        
        # ترتيب بناءً على الدقة أولاً، ثم عدد الإجابات الصحيحة
        rows.sort(key=lambda x: (
            -(x['accuracy'] or 0),  # الدقة الأعلى أولاً
            -x['correct'],          # ثم عدد الإجابات الصحيحة
            -x['score'],            # ثم النقاط
            x['display_name']       # وأخيراً الاسم
        ))
        
        # حساب الترتيب مع معالجة التعادل
        current_rank = 1
        for i, r in enumerate(rows):
            if i == 0:
                r['rank'] = current_rank
            else:
                prev_row = rows[i-1]
                # تغيير الترتيب فقط إذا تغيرت الدقة أو عدد الإجابات الصحيحة
                if (r['accuracy'] != prev_row['accuracy'] or 
                    r['correct'] != prev_row['correct']):
                    current_rank = i + 1
                r['rank'] = current_rank
        
        print(f"عدد الصفوف النهائية في الليدر بورد: {len(rows)}")
        if rows:
            print(f"أول طالب: {rows[0]['display_name']} - امتحانات: {rows[0]['exams']}")
            print(f"آخر طالب: {rows[-1]['display_name']} - امتحانات: {rows[-1]['exams']}")
        
        return rows
        
    except Exception as e:
        # في حالة حدوث خطأ، نعيد قائمة فارغة
        print(f"خطأ في حساب الليدر بورد: {e}")
        return []

@login_required
def complaint(request):
    # الحصول على الطالب من المستخدم المسجل
    from core.services.user_service import UserService
    user_service = UserService()
    student = user_service.get_or_create_student(request.user)
    if request.method=='POST':
        cats=request.POST.getlist('category'); txt=request.POST.get('text','').strip()
        if not txt and not cats: messages.error(request,"لا يمكن إرسال شكوى فارغة.")
        else:
            prefix=f"[{', '.join(cats)}] " if cats else ''
            Complaint.objects.create(student=student,text=prefix+txt if txt else prefix)
            messages.success(request,"📝 تم إرسال الشكوى/الاقتراح بنجاح. شكراً لك على مساعدتنا في تحسين المنصة!")
            return redirect('core:main_menu')
    return render(request,'core/complaint.html',{'student':student,'types':COMPLAINT_TYPES,'hide_footer':False})

def test_catalog(request):
    tests=[
        {"key":"similar_count","title":" عدد مواضع المتشابهات","desc":"يعرض عبارة ويطلب عدد مواضعها الصحيحة في نطاقك.","available":True,"url":reverse("tests:similar_count:selection")},
        {"key":"similar_on_pages","title":"مواضع المتشابهات في الصفحات","desc":"اختيار النطاق ثم تحديد الصفحات والمواضع لكل سؤال.","available":False,"url":reverse("tests:similar_on_pages:selection")},
        {"key":"verse_location_quarters","title":"موقع الآية في الربع والصفحة","desc":"اختبار تحديد موقع الآية في الربع والصفحة مع نظام صعوبة يعتمد على طول الآية.","available":False,"url":reverse("tests:verse_location_quarters:selection")},
        {"key":"page_edges_quarters","title":"بداية ونهاية الصفحات مع الأرباع","desc":"استنتاج بدايات/نهايات الآيات بين الصفحات داخل نطاقك.","available":False},
        {"key":"order_juz_quarters","title":"اختبار ترتيب الأجزاء والأرباع","desc":"أسئلة لقياس ترتيب الأجزاء والأرباع وتسلسلها.","available":False},
        {"key":"semantic_similarities","title":"متشابهات معاني الآيات","desc":"أسئلة على التشابه الدلالي للمعاني.","available":False}
    ]
    return render(request,"core/test_catalog.html",{"tests":tests,"hide_footer":False})

@login_required
def test_selection(request):
    sid=request.session.get('student_id')
    if not sid: messages.warning(request,"الرجاء إدخال اسمك أولاً."); return redirect('core:login')
    student=get_object_or_404(Student,id=sid)
    test_type_qs=request.GET.get('type')
    if test_type_qs: request.session['selected_test_type']=test_type_qs
    if not request.session.get('selected_test_type'): request.session['selected_test_type']='similar_count'
    if request.method=='POST':
        sel_juz=request.POST.getlist('selected_juz'); sel_q=request.POST.getlist('selected_quarters')
        try: num_q=int(request.POST.get('num_questions',5))
        except ValueError: num_q=5
        if num_q not in [5,10,15,20]: num_q=5
        difficulty=request.POST.get('difficulty','mixed')
        sel_juz=[int(j) for j in sel_juz if str(j).isdigit()]; sel_q=[int(q) for q in sel_q if str(q).isdigit()]
        if not sel_juz and not sel_q: messages.error(request,"لازم تختار جزء أو رُبع."); return redirect('core:test_selection')
        
        # إضافة خيار ترتيب المواضع فقط لاختبار مواضع المتشابهات في الصفحات
        session_data = {'selected_juz':sel_juz,'selected_quarters':sel_q,'num_questions':num_q,'difficulty':difficulty,'test_index':0,'score':0}
        
        # إذا كان نوع الاختبار هو مواضع المتشابهات في الصفحات، أضف خيار الترتيب
        if request.session.get('selected_test_type') == 'similar_on_pages':
            position_order = request.POST.get('position_order', 'normal')
            session_data['position_order'] = position_order
        
        request.session.update(session_data)
        request.session.pop('scope_label',None); return redirect('core:start_test')
    juz_list=Juz.objects.all().order_by('number'); juz_quarters_map={}
    for j in juz_list:
        qs=list(Quarter.objects.filter(juz=j).order_by('index_in_juz')); first_label=qs[0].label if qs else ''
        juz_quarters_map[j]={'quarters':qs,'first_label':first_label}
    return render(request,'core/test_selection.html',{'student':student,'juz_quarters_map':juz_quarters_map,'num_questions_options':[5,10,15,20],'show_splash':True,'hide_footer':False,'selected_test_type':request.session.get('selected_test_type','similar_count')})

def create_verse_location_questions(ayat_qs, desired_count, difficulty):
    """
    إنشاء أسئلة موقع الآية في الربع والصفحة
    """
    import random
    import math
    
    # الحصول على الآيات مع معلومات الربع والصفحة
    print(f"🔍 بداية إنشاء أسئلة موقع الآية...")
    print(f"   - عدد الآيات المتاحة: {ayat_qs.count()}")
    
    # الحصول على الآيات مع معلومات الربع والصفحة
    ayat_with_info = ayat_qs.select_related('quarter', 'page').values(
        'id', 'text', 'surah', 'number', 'quarter__index_in_juz', 
        'quarter__juz__number', 'page__number'
    )
    
    # حساب رقم الربع الإجمالي في القرآن كله
    for ayah in ayat_with_info:
        juz_number = ayah['quarter__juz__number']
        quarter_in_juz = ayah['quarter__index_in_juz']
        # الربع الإجمالي = (رقم الجزء - 1) * 4 + رقم الربع في الجزء
        total_quarter_number = (juz_number - 1) * 4 + quarter_in_juz
        ayah['total_quarter_number'] = total_quarter_number
        # إضافة معلومات إضافية للتصحيح
        ayah['juz_number'] = juz_number
        ayah['quarter_in_juz'] = quarter_in_juz
    
    # عرض عينة من الآيات للتحقق
    sample_ayat = list(ayat_with_info[:3])
    print(f"   - عينة من الآيات:")
    for ayah in sample_ayat:
        print(f"     * ID: {ayah['id']}, سورة: {ayah['surah']}, آية: {ayah['number']}")
        print(f"       الربع في الجزء: {ayah['quarter__index_in_juz']}, الجزء: {ayah['quarter__juz__number']}")
        print(f"       الربع الإجمالي: {ayah['total_quarter_number']}")
        print(f"       النص: {ayah['text'][:30]}...")
        # إضافة معلومات تشخيصية إضافية
        juz_num = ayah['quarter__juz__number']
        quarter_in_juz = ayah['quarter__index_in_juz']
        calculated_total = (juz_num - 1) * 8 + quarter_in_juz
        print(f"       التحقق: (الجزء {juz_num} - 1) × 8 + الربع {quarter_in_juz} = {calculated_total}")
        if calculated_total != ayah['total_quarter_number']:
            print(f"       ⚠️ خطأ في الحساب! المتوقع: {calculated_total}, المحسوب: {ayah['total_quarter_number']}")
        print()
    
    # تصفية الآيات - استبعاد آيات بداية الأرباع وسورة الفاتحة كاملة
    filtered_ayat = []
    for ayah in ayat_with_info:
        # استبعاد الآية الأولى من كل ربع (آية بداية الربع)
        if ayah['quarter__index_in_juz'] == 1 and ayah['number'] == 1:
            continue
        # استبعاد سورة الفاتحة كاملة
        if ayah['surah'] == 1:
            continue
        filtered_ayat.append(ayah)
    
    if len(filtered_ayat) < desired_count:
        return []
    
    # تصنيف الآيات حسب الصعوبة (طول الآية)
    def get_difficulty(ayah_text):
        word_count = len(ayah_text.split())
        if word_count <= 3:
            return 'hard'
        elif word_count <= 6:
            return 'medium'
        else:
            return 'easy'
    
    # تصنيف الآيات
    easy_ayat = []
    medium_ayat = []
    hard_ayat = []
    
    for ayah in filtered_ayat:
        diff = get_difficulty(ayah['text'])
        if diff == 'easy':
            easy_ayat.append(ayah)
        elif diff == 'medium':
            medium_ayat.append(ayah)
        else:
            hard_ayat.append(ayah)
    
    # اختيار الآيات حسب مستوى الصعوبة
    selected_ayat = []
    
    if difficulty == 'mixed':
        # توزيع متوازن
        ne = max(0, round(desired_count * 0.4))  # 40% سهل
        nm = max(0, round(desired_count * 0.45))  # 45% متوسط
        nh = max(0, desired_count - ne - nm)      # الباقي صعب
        
        selected_ayat.extend(random.sample(easy_ayat, min(ne, len(easy_ayat))))
        selected_ayat.extend(random.sample(medium_ayat, min(nm, len(medium_ayat))))
        selected_ayat.extend(random.sample(hard_ayat, min(nh, len(hard_ayat))))
        
        # إكمال العدد المطلوب من أي فئة متاحة
        remaining = desired_count - len(selected_ayat)
        if remaining > 0:
            all_available = easy_ayat + medium_ayat + hard_ayat
            additional = random.sample(all_available, min(remaining, len(all_available)))
            selected_ayat.extend(additional)
    
    else:
        # اختيار من مستوى واحد
        if difficulty == 'easy':
            pool = easy_ayat
        elif difficulty == 'medium':
            pool = medium_ayat
        else:  # hard
            pool = hard_ayat
        
        if len(pool) < desired_count:
            return []
        
        selected_ayat = random.sample(pool, desired_count)
    
    # إنشاء الأسئلة
    questions = []
    for ayah in selected_ayat:
        # حساب موقع الآية في الربع
        current_quarter = ayah['total_quarter_number']  # استخدام الربع الإجمالي
        current_page = ayah['page__number']
        
        # التأكد من أن الربع موجود
        if current_quarter is None:
            print(f"⚠️ تحذير: الآية {ayah['id']} (سورة {ayah['surah']}:{ayah['number']}) لا تحتوي على معلومات الربع")
            continue
        
        print(f"🔍 الآية: {ayah['text'][:50]}...")
        print(f"   - الربع الإجمالي: {current_quarter}")
        print(f"   - الصفحة: {current_page}")
        
        # حساب الصفحة داخل الربع
        # نحتاج للحصول على صفحة بداية الربع
        current_juz = ayah['juz_number']
        current_quarter_in_juz = ayah['quarter_in_juz']
        
        # البحث عن صفحة بداية الربع
        quarter_start_page = None
        try:
            # البحث عن أول آية في الربع
            quarter_start_ayah = Ayah.objects.filter(
                quarter__juz__number=current_juz,
                quarter__index_in_juz=current_quarter_in_juz
            ).order_by('surah', 'number').first()
            
            if quarter_start_ayah and quarter_start_ayah.page:
                quarter_start_page = quarter_start_ayah.page.number
                print(f"   📖 صفحة بداية الربع: {quarter_start_page}")
            else:
                print(f"   ⚠️ تحذير: لا يمكن العثور على صفحة بداية الربع")
                continue
                
        except Exception as e:
            print(f"   ⚠️ خطأ في البحث عن صفحة بداية الربع: {e}")
            continue
        
        # حساب الصفحة داخل الربع
        if quarter_start_page and current_page:
            page_difference = current_page - quarter_start_page
            if page_difference == 0:
                correct_page_in_quarter = 1  # الصفحة الأولى
            elif page_difference == 1:
                correct_page_in_quarter = 2  # الصفحة الثانية
            elif page_difference == 2:
                correct_page_in_quarter = 3  # الصفحة الثالثة
            elif page_difference == 3:
                correct_page_in_quarter = 4  # الصفحة الرابعة
            elif page_difference > 3:
                # إذا كانت الفجوة أكبر من 3 صفحات، نحسب الصفحة بناءً على الفجوة
                # نعتبر أن كل 4 صفحات = ربع جديد
                if page_difference <= 7:
                    correct_page_in_quarter = 1  # الصفحة الأولى من الربع التالي
                elif page_difference <= 11:
                    correct_page_in_quarter = 2  # الصفحة الثانية من الربع التالي
                elif page_difference <= 15:
                    correct_page_in_quarter = 3  # الصفحة الثالثة من الربع التالي
                else:
                    correct_page_in_quarter = 4  # الصفحة الرابعة من الربع التالي
                print(f"   📄 فجوة كبيرة ({page_difference} صفحات)، تم حساب الصفحة: {correct_page_in_quarter}")
            else:
                # إذا كانت الفجوة سالبة (الصفحة قبل بداية الربع)، نعتبرها الصفحة الأولى
                correct_page_in_quarter = 1
                print(f"   ⚠️ تحذير: الصفحة قبل بداية الربع ({page_difference})، تم تعيينها كصفحة أولى")
        else:
            # إذا لم نتمكن من الحساب، نستخدم الصفحة الأولى كافتراضي
            correct_page_in_quarter = 1
            print(f"   ⚠️ تحذير: تم استخدام الصفحة الأولى كافتراضي")
        
        print(f"   📄 الصفحة في الربع: {correct_page_in_quarter}")
        
        # إنشاء خيارات للأرباع المحيطة بالربع الصحيح
        quarter_options = []
        
        # إضافة الربع الصحيح أولاً
        quarter_options.append(current_quarter)
        print(f"   ✅ الربع الصحيح: {current_quarter} (الجزء {ayah['juz_number']}, الربع {ayah['quarter_in_juz']})")
        
        # إضافة أرباع من نفس الجزء أولاً (أكثر منطقية)
        current_juz = ayah['juz_number']
        current_quarter_in_juz = ayah['quarter_in_juz']
        
        # إضافة ربع سابق من نفس الجزء
        if current_quarter_in_juz > 1:
            prev_quarter_in_juz = current_quarter_in_juz - 1
            prev_total_quarter = (current_juz - 1) * 4 + prev_quarter_in_juz
            quarter_options.append(prev_total_quarter)
            print(f"   ➕ ربع سابق من نفس الجزء: {prev_total_quarter} (الجزء {current_juz}, الربع {prev_quarter_in_juz})")
        
        # إضافة ربع لاحق من نفس الجزء
        if current_quarter_in_juz < 4:
            next_quarter_in_juz = current_quarter_in_juz + 1
            next_total_quarter = (current_juz - 1) * 4 + next_quarter_in_juz
            quarter_options.append(next_total_quarter)
            print(f"   ➕ ربع لاحق من نفس الجزء: {next_total_quarter} (الجزء {current_juz}, الربع {next_quarter_in_juz})")
        
        # إضافة أرباع إضافية إذا لم نصل لـ 4 خيارات
        while len(quarter_options) < 4:
            # محاولة إضافة ربع من جزء مجاور (أقرب)
            if current_juz > 1 and len(quarter_options) < 4:
                # ربع من الجزء السابق (نفس رقم الربع)
                prev_juz_quarter = (current_juz - 2) * 4 + current_quarter_in_juz
                if prev_juz_quarter > 0 and prev_juz_quarter not in quarter_options:
                    quarter_options.append(prev_juz_quarter)
                    print(f"   ➕ ربع من جزء سابق: {prev_juz_quarter} (الجزء {current_juz - 1}, الربع {current_quarter_in_juz})")
                    continue
            
            if current_juz < 30 and len(quarter_options) < 4:
                # ربع من الجزء التالي (نفس رقم الربع)
                next_juz_quarter = current_juz * 4 + current_quarter_in_juz
                if next_juz_quarter <= 120 and next_juz_quarter not in quarter_options:
                    quarter_options.append(next_juz_quarter)
                    print(f"   ➕ ربع من جزء تالي: {next_juz_quarter} (الجزء {current_juz + 1}, الربع {current_quarter_in_juz})")
                    continue
            
            # محاولة إضافة أرباع من نفس الجزء مع فجوات صغيرة
            if current_quarter_in_juz > 2 and len(quarter_options) < 4:
                far_prev_quarter = (current_juz - 1) * 4 + (current_quarter_in_juz - 2)
                if far_prev_quarter > 0 and far_prev_quarter not in quarter_options:
                    quarter_options.append(far_prev_quarter)
                    print(f"   ➕ ربع بعيد سابق من نفس الجزء: {far_prev_quarter} (الجزء {current_juz}, الربع {current_quarter_in_juz - 2})")
                    continue
            
            if current_quarter_in_juz < 3 and len(quarter_options) < 4:
                far_next_quarter = (current_juz - 1) * 4 + (current_quarter_in_juz + 2)
                if far_next_quarter <= 120 and far_next_quarter not in quarter_options:
                    quarter_options.append(far_next_quarter)
                    print(f"   ➕ ربع بعيد لاحق من نفس الجزء: {far_next_quarter} (الجزء {current_juz}, الربع {current_quarter_in_juz + 2})")
                    continue
            
            # إذا لم نتمكن من إضافة أرباع منطقية، نضيف أرباع قريبة
            if len(quarter_options) < 4:
                # إضافة ربع من جزء مجاور مع رقم ربع مختلف
                if current_juz > 1:
                    for offset in [-1, 1]:  # ربع سابق أو لاحق
                        if current_quarter_in_juz + offset >= 1 and current_quarter_in_juz + offset <= 4:
                            adj_quarter = (current_juz - 2) * 4 + (current_quarter_in_juz + offset)
                            if adj_quarter > 0 and adj_quarter not in quarter_options:
                                quarter_options.append(adj_quarter)
                                print(f"   ➕ ربع مجاور: {adj_quarter} (الجزء {current_juz - 1}, الربع {current_quarter_in_juz + offset})")
                                break
                
                if len(quarter_options) < 4 and current_juz < 30:
                    for offset in [-1, 1]:  # ربع سابق أو لاحق
                        if current_quarter_in_juz + offset >= 1 and current_quarter_in_juz + offset <= 4:
                            adj_quarter = current_juz * 4 + (current_quarter_in_juz + offset)
                            if adj_quarter <= 120 and adj_quarter not in quarter_options:
                                quarter_options.append(adj_quarter)
                                print(f"   ➕ ربع مجاور: {adj_quarter} (الجزء {current_juz + 1}, الربع {current_quarter_in_juz + offset})")
                                break
            
            # إذا لم نتمكن من إضافة أرباع منطقية، نضيف أي ربع متاح
            if len(quarter_options) < 4:
                for i in range(1, 121):
                    if i not in quarter_options:
                        quarter_options.append(i)
                        print(f"   ➕ ربع متاح: {i}")
                        break
        
        print(f"   📋 الخيارات النهائية: {quarter_options}")
        
        # ترتيب عشوائي لخيارات الأرباع
        random.shuffle(quarter_options)
        
        # إضافة معلومات تشخيصية إضافية
        print(f"   🔍 تحليل الخيارات:")
        for i, quarter_num in enumerate(quarter_options, 1):
            juz_num = ((quarter_num - 1) // 4) + 1
            quarter_in_juz = ((quarter_num - 1) % 4) + 1
            print(f"      {i}. الربع {quarter_num} = الجزء {juz_num}, الربع {quarter_in_juz}")
        
        # إنشاء خيارات للصفحات داخل الربع (الأولى، الثانية، الثالثة، الرابعة)
        page_in_quarter_options = [1, 2, 3, 4]  # الصفحة الأولى، الثانية، الثالثة، الرابعة
        
        question = {
            'ayah_id': ayah['id'],
            'ayah_text': ayah['text'],
            'correct_quarter': current_quarter,
            'quarter_options': quarter_options,
            'correct_page_in_quarter': correct_page_in_quarter,
            'page_in_quarter_options': page_in_quarter_options,
            'given_answer': None,
            'question_type': 'verse_location_quarters',
            'stage': 'combined_selection',  # المرحلة المشتركة: اختيار الربع والصفحة
            # إضافة معلومات إضافية للتصحيح
            'juz_number': ayah['juz_number'],
            'quarter_in_juz': ayah['quarter_in_juz'],
            'quarter_start_page': quarter_start_page,  # إضافة صفحة بداية الربع للتصحيح
            'current_page': current_page  # إضافة الصفحة الحالية للتصحيح
        }
        questions.append(question)
        print(f"   ✅ تم إنشاء السؤال بنجاح")
        print(f"      - الآية: {ayah['text'][:50]}...")
        print(f"      - الربع الصحيح: {current_quarter} (الجزء {ayah['juz_number']}, الربع {ayah['quarter_in_juz']})")
        print(f"      - صفحة بداية الربع: {quarter_start_page}")
        print(f"      - الصفحة الحالية: {current_page}")
        print(f"      - الصفحة في الربع: {correct_page_in_quarter}")
        print(f"      - الخيارات: {quarter_options}")
        print()
    
    return questions[:desired_count]

@login_required
def start_test(request):
    import math
    sid=request.session.get('student_id')
    if not sid: messages.warning(request,"الرجاء إدخال اسمك أولاً."); return redirect('core:login')
    student=get_object_or_404(Student,id=sid)
    juz_ids=request.session.get('selected_juz',[]); q_ids=request.session.get('selected_quarters',[])
    desired=int(request.session.get('num_questions',5)); difficulty=request.session.get('difficulty','mixed')
    if q_ids: ayat_qs=Ayah.objects.filter(quarter_id__in=q_ids)
    elif juz_ids: ayat_qs=Ayah.objects.filter(quarter__juz__number__in=juz_ids)
    else: messages.error(request,"مفيش نطاق محدد."); return redirect('core:test_selection')
    if not ayat_qs.exists(): messages.error(request,"النطاق لا يحتوى آيات."); return redirect('core:test_selection')

    ayat_ids=list(ayat_qs.values_list('id',flat=True)); MAX_OCC_SCOPE=60
    
    # إضافة معلومات تشخيصية
    print(f"🔍 البحث عن العبارات المتشابهة:")
    print(f"   - عدد الآيات في النطاق: {len(ayat_ids)}")
    print(f"   - النطاق: {juz_ids if juz_ids else q_ids}")
    print(f"   - أول 5 معرفات آيات: {ayat_ids[:5]}")
    
    # فحص التكرارات قبل التجميع
    all_occ = PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids)
    print(f"   - إجمالي التكرارات في النطاق: {all_occ.count()}")
    
    stats=(PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids).values('phrase_id')
           .annotate(freq=Count('id')).filter(freq__gte=2,freq__lte=MAX_OCC_SCOPE))
    
    print(f"   - عدد العبارات المتشابهة الموجودة: {len(stats)}")
    print(f"   - MAX_OCC_SCOPE: {MAX_OCC_SCOPE}")
    
    if not stats: 
        # محاولة البحث مع معايير أقل صرامة
        print("   ⚠️ لم يتم العثور على عبارات، جاري البحث بمعايير أقل صرامة...")
        stats_loose=(PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids).values('phrase_id')
                    .annotate(freq=Count('id')).filter(freq__gte=2))
        print(f"   - عدد العبارات مع معايير أقل صرامة: {len(stats_loose)}")
        
        if not stats_loose:
            messages.error(request,"مافيش عبارات متشابهة كافية فى النطاق المحدد. جرب نطاق أوسع أو أجزاء مختلفة.")
            return redirect('core:test_selection')
        else:
            stats = stats_loose

    phrase_ids=[s['phrase_id'] for s in stats]; freq_map={s['phrase_id']:s['freq'] for s in stats}
    
    print(f"   - العبارات المختارة: {len(phrase_ids)}")
    
    occ_rows=PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids,phrase_id__in=phrase_ids).values('phrase_id','ayah_id')
    occ_by_phrase={};
    for r in occ_rows: occ_by_phrase.setdefault(r['phrase_id'],set()).add(r['ayah_id'])
    
    phrases={p.id:p for p in Phrase.objects.filter(id__in=phrase_ids)}
    sorted_pids=sorted(phrase_ids,key=lambda pid:(-phrases[pid].length_words,-freq_map[pid],phrases[pid].text))
    
    print(f"   - العبارات بعد الترتيب: {len(sorted_pids)}")
    
    kept,kept_sets=[],[];
    for pid in sorted_pids:
        aset=occ_by_phrase[pid]
        if any(aset.issubset(S) for S in kept_sets): continue
        kept.append(pid); kept_sets.append(aset)
    
    print(f"   - العبارات النهائية بعد إزالة التكرار: {len(kept)}")

    def bucket(ph_len,freq):
        if ph_len>=5 and 2<=freq<=3: return 'easy'
        if ph_len>=4 and 2<=freq<=6: return 'medium'
        if ph_len>=3 and 7<=freq<=60: return 'hard'
        return 'other'

    candidates=[]
    for pid in kept:
        ph=phrases[pid]; freq=freq_map[pid]; b=bucket(ph.length_words,freq)
        if b=='other': continue
        ayahs=(Ayah.objects.filter(id__in=occ_by_phrase[pid]).select_related('quarter__juz').order_by('surah','number'))
        literal=[{'surah':a.surah,'surah_name':a.surah,'number':a.number,'juz_number':a.quarter.juz.number if a.quarter else None,'quarter_label':a.quarter.label if a.quarter else None,'text':a.text} for a in ayahs]
        candidates.append({'phrase_id':pid,'phrase_text':ph.text,'correct_count':freq,'occurrence_ayah_ids':list(occ_by_phrase[pid]),'literal_ayahs':literal,'bucket':b,'score':freq*math.log(1+ph.length_words)})

    print(f"   - المرشحون للأسئلة: {len(candidates)}")
    
    if not candidates: 
        print("   ⚠️ لا توجد مرشحين، جاري البحث بمعايير أقل صرامة...")
        # محاولة البحث بمعايير أقل صرامة
        for pid in kept:
            ph = phrases[pid]; freq = freq_map[pid]
            # قبول جميع العبارات بغض النظر عن مستوى الصعوبة
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
                'bucket': 'easy',  # افتراضي
                'score': freq * math.log(1 + ph.length_words),
            })
        
        print(f"   - المرشحون بعد المعايير المخففة: {len(candidates)}")
        
        if not candidates:
            messages.error(request,"لا توجد عبارات متشابهة في النطاق المحدد. جرب نطاق أوسع أو أجزاء مختلفة.")
            return redirect('core:test_selection')

    if difficulty=='mixed':
        E=[c for c in candidates if c['bucket']=='easy']; M=[c for c in candidates if c['bucket']=='medium']; H=[c for c in candidates if c['bucket']=='hard']
        random.shuffle(E); random.shuffle(M); random.shuffle(H)
        ne=max(0,round(desired*0.40)); nm=max(0,round(desired*0.45)); nh=max(0,desired-ne-nm)
        take=E[:ne]+M[:nm]+H[:nh]
        for pool in [M[nm:],E[ne:],H[nh:]]:
            if len(take)>=desired: break
            need=desired-len(take); take+=pool[:need]
        selected=take[:desired]; random.shuffle(selected)
    else:
        filtered=[c for c in candidates if c['bucket']==difficulty]
        if not filtered: messages.error(request,"لا توجد أسئلة مناسبة لهذا المستوى في النطاق."); return redirect('core:test_selection')
        filtered.sort(key=lambda x:(-x['score'],x['phrase_text'])); selected=filtered[:desired]

    selected_type=request.session.get('selected_test_type','similar_count')
    
    # إنشاء أسئلة مختلفة حسب نوع الاختبار
    if selected_type == 'verse_location_quarters':
        # إنشاء أسئلة موقع الآية في الربع والصفحة
        questions = create_verse_location_questions(ayat_qs, desired, difficulty)
        if not questions:
            messages.error(request, "لا يمكن إنشاء أسئلة مناسبة لهذا النوع من الاختبار في النطاق المحدد.")
            return redirect('core:test_selection')
    else:
        # النوع التقليدي - أسئلة المتشابهات
        questions = [{'phrase_id':c['phrase_id'],'phrase_text':c['phrase_text'],'correct_count':c['correct_count'],'occurrence_ayah_ids':c['occurrence_ayah_ids'],'literal_ayahs':c['literal_ayahs'],'given_answer':None} for c in selected]
    
    session_db=TestSession.objects.create(student=student,test_type=selected_type,num_questions=len(questions),difficulty=difficulty,completed=False)
    if juz_ids: session_db.juzs.add(*Juz.objects.filter(number__in=juz_ids))
    if q_ids: session_db.quarters.add(*Quarter.objects.filter(id__in=q_ids))

    request.session['db_session_id']=session_db.id
    db_qids=[TestQuestion.objects.create(session=session_db).id for _ in questions]
    request.session['db_question_ids']=db_qids
    request.session['scope_label']=_build_scope_label(juz_ids,q_ids)
    request.session['questions']=questions
    request.session['test_index']=0; request.session['score']=0

    # تهيئة تدفّق هذا الاختبار (namespaced)
    total=len(questions); ns=_ns(request,f'flow:{session_db.id}')
    request.session[ns]={'current':1,'total':int(total)}; request.session.modified=True

    # اختياري: تهيئة قديمة للحفاظ على التوافق لو عندك كود لسه بيقرأ pages_flow
    request.session[_ns(request,'pages_flow')]={'current':1,'total':int(total)}; request.session.modified=True
    
    # مسح الأجزاء والأرباع المحظورة عند بداية اختبار جديد
    if 'disabled_juz' in request.session:
        del request.session['disabled_juz']
    if 'disabled_quarters' in request.session:
        del request.session['disabled_quarters']
    
    print("=== بداية اختبار جديد - مسح الأجزاء والأرباع المحظورة ===")

    # إشعار بدء الاختبار
    selected_type = request.session.get('selected_test_type', 'similar_count')
    test_name = {
        'similar_count': 'عدد مواضع المتشابهات',
        'similar_on_pages': 'مواضع المتشابهات في الصفحات',
        'verse_location_quarters': 'موقع الآية في الربع والصفحة'
    }.get(selected_type, 'اختبار الحفظ')
    
    messages.success(request, f"🚀 تم بدء اختبار {test_name} بنجاح! ({len(questions)} أسئلة)")

    # التحقق من نوع الاختبار وتوجيه للمسار المناسب
    if selected_type == 'similar_count':
        return redirect('tests:similar_count:question')
    elif selected_type == 'similar_on_pages':
        return redirect('tests:similar_on_pages:question')
    elif selected_type == 'verse_location_quarters':
        return redirect('tests:verse_location_quarters:question')
    else:
        return redirect('core:test_question')

# helper صغير يجيب تدفّق الاختبار الحالي (current/total) من الـsession
def _current_flow(request):
    tid=request.session.get('db_session_id')
    return request.session.get(_ns(request,f'flow:{tid}')) or {}


@login_required
def test_question(request):
    sid=request.session.get('student_id')
    if not sid: messages.warning(request,"الرجاء إدخال اسمك أولاً."); return redirect('core:login')
    student=get_object_or_404(Student,id=sid); idx=request.session.get('test_index',0); qs=request.session.get('questions',[]); total=len(qs)
    
    # تسجيل للتشخيص
    print(f"🔍 DEBUG: test_question - idx: {idx}, total: {total}")
    print(f"🔍 DEBUG: selected_type: {request.session.get('selected_test_type', 'similar_count')}")
    if idx < total:
        print(f"🔍 DEBUG: current question: {qs[idx] if qs else 'No questions'}")
    if idx>=total:
        score=request.session.get('score',0); scope_lbl=request.session.get('scope_label','')
        selected_type = request.session.get('selected_test_type', 'similar_count')
        
        if selected_type == 'verse_location_quarters':
            # إنشاء تفاصيل نتائج اختبار موقع الآية
            detailed = []
            for q in qs:
                if q.get('question_type') == 'verse_location_quarters':
                    detailed.append({
                        'ayah_text': q.get('ayah_text', ''),
                        'ayah_text_full': q.get('ayah_text', ''),  # نص الآية الكامل للتلوين
                        'correct_quarter': q.get('correct_quarter', ''),
                        'quarter_answer': q.get('quarter_answer'),
                        'quarter_is_correct': q.get('quarter_is_correct', False),
                        'correct_page_in_quarter': q.get('correct_page_in_quarter', ''),
                        'page_answer': q.get('page_answer'),
                        'page_is_correct': q.get('page_is_correct', False),
                        'quarter_start_page': q.get('quarter_start_page'),
                        'current_page': q.get('current_page'),
                        'juz_number': q.get('juz_number'),
                        'quarter_in_juz': q.get('quarter_in_juz'),
                        'question_type': 'verse_location_quarters'
                    })
                else:
                    # الأسئلة التقليدية
                    detailed.append({
                        'phrase': q.get('phrase_text') or q.get('phrase', ''),
                        'correct_count': q.get('correct_count'),
                        'given_answer': q.get('given_answer'),
                        'occurrences': q.get('literal_ayahs', [])
                    })
        else:
            # النوع التقليدي
            detailed=[{'phrase':q.get('phrase_text') or q.get('phrase',''),'correct_count':q.get('correct_count'),'given_answer':q.get('given_answer'),'occurrences':q.get('literal_ayahs',[])} for q in qs]
        
        wrong=max(0,total-score); db_sid=request.session.get('db_session_id')
        if db_sid: 
            from django.utils import timezone
            TestSession.objects.filter(id=db_sid).update(
                completed=True,
                completed_at=timezone.now()
            )
        
        # إشعار إنهاء الاختبار
        percentage = round((score / total) * 100) if total > 0 else 0
        if percentage >= 90:
            emoji = "🏆"
            message = f"ممتاز! حصلت على {score}/{total} ({percentage}%)"
        elif percentage >= 70:
            emoji = "🎉"
            message = f"جيد جداً! حصلت على {score}/{total} ({percentage}%)"
        elif percentage >= 50:
            emoji = "👍"
            message = f"ليس سيئاً! حصلت على {score}/{total} ({percentage}%)"
        else:
            emoji = "💪"
            message = f"حاول مرة أخرى! حصلت على {score}/{total} ({percentage}%)"
        
        messages.success(request, f"{emoji} تم إنهاء الاختبار! {message}")
        
        # حفظ بيانات النتائج في السيشن للعرض في صفحة منفصلة
        request.session['test_results'] = {
            'student_id': student.id,
            'score': score,
            'total': total,
            'detailed_results': detailed,
            'scope_label': scope_lbl,
            'wrong': wrong,
            'test_type': selected_type
        }
        
        for k in ['questions','test_index','score','selected_juz','selected_quarters','num_questions','scope_label','difficulty','db_session_id','db_question_ids']: request.session.pop(k,None)
        
        # التحقق من نوع الاختبار وتوجيه لصفحة النتائج المناسبة
        if selected_type == 'similar_count':
            return redirect('tests:similar_count:result')
        elif selected_type == 'similar_on_pages':
            return redirect('tests:similar_on_pages:result')
        elif selected_type == 'verse_location_quarters':
            return redirect('tests:verse_location_quarters:result')
        else:
            return render(request,'core/test_result.html',{
                'student':student,
                'score':score,
                'total':total,
                'detailed_results':detailed,
                'scope_label':scope_lbl,
                'wrong':wrong,
                'test_type': selected_type,
                'hide_footer':True
            })
    question=qs[idx]; progress=round((idx+1)/total*100) if total else 0
    if request.method=='POST' and request.POST.get('action')=='end':
        db_sid=request.session.get('db_session_id')
        if db_sid: TestSession.objects.filter(id=db_sid).update(completed=True)
        request.session['test_index']=len(qs)
        # التحقق من نوع الاختبار وتوجيه للمسار المناسب
        selected_type = request.session.get('selected_test_type', 'similar_count')
        if selected_type == 'similar_count':
            return redirect('tests:similar_count:question')
        else:
            return redirect('core:test_question')
    if request.method=='POST':
        selected_type=request.session.get('selected_test_type','similar_count')
        
        if selected_type == 'verse_location_quarters':
            # معالجة أسئلة موقع الآية
            question = qs[idx]
            stage = request.POST.get('stage') or question.get('stage', 'combined_selection')
            
            # التحقق من وجود تحقق فوري
            if question.get('show_feedback') and question.get('feedback_stage') == 'quarter':
                # عرض التحقق من الربع
                correct_quarter = question.get('correct_quarter', '')
                quarter_answer = question.get('quarter_answer')
                quarter_is_correct = question.get('quarter_is_correct', False)
                
                context = {
                    'student': student,
                    'question_number': idx + 1,
                    'total_questions': total,
                    'ayah_text': question.get('ayah_text', ''),
                    'correct_quarter': correct_quarter,
                    'quarter_answer': quarter_answer,
                    'quarter_is_correct': quarter_is_correct,
                    'scope_label': request.session.get('scope_label', ''),
                    'progress_percent': progress,
                    'question_type': 'verse_location_quarters',
                    'stage': 'quarter_feedback',
                    'submitted': False,
                    'hide_footer': True
                }
                
                return render(request, 'core/verse_location_question.html', context)
            
            if question.get('show_feedback') and question.get('feedback_stage') == 'combined':
                # عرض التحقق المشترك للربع والصفحة
                correct_quarter = question.get('correct_quarter', '')
                correct_page_in_quarter = question.get('correct_page_in_quarter', 1)
                quarter_answer = question.get('quarter_answer')
                page_answer = question.get('page_answer')
                quarter_is_correct = question.get('quarter_is_correct', False)
                page_is_correct = question.get('page_is_correct', False)
                
                context = {
                    'student': student,
                    'question_number': idx + 1,
                    'total_questions': total,
                    'ayah_text': question.get('ayah_text', ''),
                    'correct_quarter': correct_quarter,
                    'correct_page_in_quarter': correct_page_in_quarter,
                    'quarter_answer': quarter_answer,
                    'page_answer': page_answer,
                    'quarter_is_correct': quarter_is_correct,
                    'page_is_correct': page_is_correct,
                    'scope_label': request.session.get('scope_label', ''),
                    'progress_percent': progress,
                    'question_type': 'verse_location_quarters',
                    'stage': 'combined_feedback',
                    'submitted': False,
                    'hide_footer': True
                }
                return render(request, 'core/verse_location_question.html', context)
            
            if question.get('show_feedback') and question.get('feedback_stage') == 'page':
                correct_page_in_quarter = question.get('correct_page_in_quarter', 1)
                page_answer = question.get('page_answer')
                page_is_correct = question.get('page_is_correct', False)
                context = {
                    'student': student,
                    'question_number': idx + 1,
                    'total_questions': total,
                    'ayah_text': question.get('ayah_text', ''),
                    'correct_page_in_quarter': correct_page_in_quarter,
                    'page_answer': page_answer,
                    'page_is_correct': page_is_correct,
                    'scope_label': request.session.get('scope_label', ''),
                    'progress_percent': progress,
                    'question_type': 'verse_location_quarters',
                    'stage': 'page_feedback',
                    'submitted': False,
                    'hide_footer': True
                }
                return render(request, 'core/verse_location_question.html', context)
            
            if stage == 'combined_selection':
                # المرحلة المشتركة: اختيار الربع والصفحة
                quarter_ans = request.POST.get('quarter_selection')
                page_ans = request.POST.get('page_in_quarter_selection')
                
                try:
                    qs[idx]['quarter_answer'] = int(quarter_ans) if quarter_ans and quarter_ans.isdigit() else None
                except (ValueError, TypeError):
                    qs[idx]['quarter_answer'] = None
                
                try:
                    qs[idx]['page_answer'] = int(page_ans) if page_ans and page_ans.isdigit() else None
                except (ValueError, TypeError):
                    qs[idx]['page_answer'] = None
                
                request.session['questions'] = qs
                
                # التحقق من صحة إجابات الربع والصفحة
                correct_quarter = question.get('correct_quarter')
                correct_page_in_quarter = question.get('correct_page_in_quarter', 1)
                quarter_answer = qs[idx]['quarter_answer']
                page_answer = qs[idx]['page_answer']
                
                # حفظ معلومات الإجابات الصحيحة للعرض لاحقاً
                qs[idx]['quarter_is_correct'] = (quarter_answer == correct_quarter)
                qs[idx]['page_is_correct'] = (page_answer is not None and page_answer == correct_page_in_quarter)
                
                # الطالب يحصل على نقطة فقط إذا كانت إجابتي الربع والصفحة صحيحتين
                quarter_is_correct = qs[idx]['quarter_is_correct']
                page_is_correct = qs[idx]['page_is_correct']
                is_completely_correct = quarter_is_correct and page_is_correct
                
                # تحديث قاعدة البيانات
                db_qids = request.session.get('db_question_ids') or []
                if isinstance(db_qids, list) and idx < len(db_qids):
                    quarter_text = "صحيح" if quarter_is_correct else f"خطأ (الصحيح: {correct_quarter})"
                    page_text = "صحيح" if page_is_correct else f"خطأ (الصحيح: {correct_page_in_quarter})"
                    
                    TestQuestion.objects.filter(id=db_qids[idx]).update(
                        student_response=f"ربع: {quarter_answer} ({quarter_text}), صفحة: {page_answer} ({page_text})",
                        is_correct=is_completely_correct
                    )
                
                # تحديث النتيجة
                if is_completely_correct:
                    request.session['score'] = request.session.get('score', 0) + 1
                
                # إضافة معلومات للتحقق الفوري
                qs[idx]['show_feedback'] = True
                qs[idx]['feedback_stage'] = 'combined'
                qs[idx]['stage'] = 'combined_feedback'
                
                request.session['questions'] = qs
                # التحقق من نوع الاختبار وتوجيه للمسار المناسب
                selected_type = request.session.get('selected_test_type', 'similar_count')
                if selected_type == 'similar_count':
                    return redirect('tests:similar_count:question')
                else:
                    return redirect('core:test_question')
            
            elif stage == 'combined_feedback':
                # الانتقال للسؤال التالي
                print(f"🔄 الانتقال من combined_feedback للسؤال التالي: {idx + 1}")
                request.session['test_index'] = idx + 1
                request.session['questions'] = qs
                # التحقق من نوع الاختبار وتوجيه للمسار المناسب
                selected_type = request.session.get('selected_test_type', 'similar_count')
                if selected_type == 'similar_count':
                    return redirect('tests:similar_count:question')
                else:
                    return redirect('core:test_question')
            
            elif stage == 'page_feedback':
                # الانتقال للسؤال التالي
                print(f"🔄 الانتقال من page_feedback للسؤال التالي: {idx + 1}")
                request.session['test_index'] = idx + 1
                request.session['questions'] = qs
                # التحقق من نوع الاختبار وتوجيه للمسار المناسب
                selected_type = request.session.get('selected_test_type', 'similar_count')
                if selected_type == 'similar_count':
                    return redirect('tests:similar_count:question')
                else:
                    return redirect('core:test_question')
            
            elif stage == 'page_selection':
                # المرحلة الثانية: اختيار الصفحة داخل الربع
                ans = request.POST.get('page_in_quarter_selection')
                try:
                    qs[idx]['page_answer'] = int(ans) if ans and ans.isdigit() else None
                except (ValueError, TypeError):
                    qs[idx]['page_answer'] = None
                
                request.session['questions'] = qs
                
                # التحقق من صحة إجابة الصفحة
                correct_page_in_quarter = question.get('correct_page_in_quarter', 1)
                page_answer = qs[idx]['page_answer']
                
                # حفظ معلومات الإجابة الصحيحة للعرض لاحقاً
                qs[idx]['page_is_correct'] = (page_answer is not None and page_answer == correct_page_in_quarter)
                
                # الطالب يحصل على نقطة فقط إذا كانت إجابتي الربع والصفحة صحيحتين
                quarter_is_correct = qs[idx].get('quarter_is_correct', False)
                page_is_correct = qs[idx]['page_is_correct']
                is_completely_correct = quarter_is_correct and page_is_correct
                
                # تحديث قاعدة البيانات
                db_qids = request.session.get('db_question_ids') or []
                if isinstance(db_qids, list) and idx < len(db_qids):
                    quarter_text = "صحيح" if quarter_is_correct else f"خطأ (الصحيح: {question.get('correct_quarter')})"
                    page_text = "صحيح" if page_is_correct else f"خطأ (الصحيح: {correct_page_in_quarter})"
                    
                    TestQuestion.objects.filter(id=db_qids[idx]).update(
                        student_response=f"ربع: {qs[idx].get('quarter_answer')} ({quarter_text}), صفحة: {page_answer} ({page_text})",
                        is_correct=is_completely_correct
                    )
                
                # تحديث النتيجة
                if is_completely_correct:
                    request.session['score'] = request.session.get('score', 0) + 1
                
                qs[idx]['show_feedback'] = True
                qs[idx]['feedback_stage'] = 'page'
                qs[idx]['stage'] = 'page_feedback'
                request.session['questions'] = qs
                # التحقق من نوع الاختبار وتوجيه للمسار المناسب
                selected_type = request.session.get('selected_test_type', 'similar_count')
                if selected_type == 'similar_count':
                    return redirect('tests:similar_count:question')
                else:
                    return redirect('core:test_question')
            
            elif stage == 'quarter_feedback':
                # الانتقال من مرحلة التحقق للمرحلة التالية
                print(f"🔄 الانتقال من quarter_feedback لـ page_selection")
                qs[idx]['stage'] = 'page_selection'
                qs[idx]['correct_quarter'] = question.get('correct_quarter')
                qs[idx]['show_feedback'] = False
                request.session['questions'] = qs
                # التحقق من نوع الاختبار وتوجيه للمسار المناسب
                selected_type = request.session.get('selected_test_type', 'similar_count')
                if selected_type == 'similar_count':
                    return redirect('tests:similar_count:question')
                else:
                    return redirect('core:test_question')
            
            elif stage == 'page_selection':
                # المرحلة الثانية: اختيار الصفحة داخل الربع
                ans = request.POST.get('page_in_quarter_selection')
                try:
                    qs[idx]['page_answer'] = int(ans) if ans and ans.isdigit() else None
                except (ValueError, TypeError):
                    qs[idx]['page_answer'] = None
                
                request.session['questions'] = qs
                
                # التحقق من صحة إجابة الصفحة
                correct_page_in_quarter = question.get('correct_page_in_quarter', 1)
                page_answer = qs[idx]['page_answer']
                
                # حفظ معلومات الإجابة الصحيحة للعرض لاحقاً
                qs[idx]['page_is_correct'] = (page_answer is not None and page_answer == correct_page_in_quarter)
                
                # الطالب يحصل على نقطة فقط إذا كانت إجابتي الربع والصفحة صحيحتين
                quarter_is_correct = qs[idx].get('quarter_is_correct', False)
                page_is_correct = qs[idx]['page_is_correct']
                is_completely_correct = quarter_is_correct and page_is_correct
                
                # تحديث قاعدة البيانات
                db_qids = request.session.get('db_question_ids') or []
                if isinstance(db_qids, list) and idx < len(db_qids):
                    quarter_text = "صحيح" if quarter_is_correct else f"خطأ (الصحيح: {question.get('correct_quarter')})"
                    page_text = "صحيح" if page_is_correct else f"خطأ (الصحيح: {correct_page_in_quarter})"
                    
                    TestQuestion.objects.filter(id=db_qids[idx]).update(
                        student_response=f"ربع: {qs[idx].get('quarter_answer')} ({quarter_text}), صفحة: {page_answer} ({page_text})",
                        is_correct=is_completely_correct
                    )
                
                # تحديث النتيجة
                if is_completely_correct:
                    request.session['score'] = request.session.get('score', 0) + 1
                
                qs[idx]['show_feedback'] = True
                qs[idx]['feedback_stage'] = 'page'
                qs[idx]['stage'] = 'page_feedback'
                request.session['questions'] = qs
                print(f"🔄 تم الانتقال لـ page_feedback")
                # التحقق من نوع الاختبار وتوجيه للمسار المناسب
                selected_type = request.session.get('selected_test_type', 'similar_count')
                if selected_type == 'similar_count':
                    return redirect('tests:similar_count:question')
                else:
                    return redirect('core:test_question')
        
        else:
            # معالجة الأسئلة التقليدية
            ans = request.POST.get('occurrence')
            try:
                qs[idx]['given_answer'] = int(ans)
            except (ValueError, TypeError):
                qs[idx]['given_answer'] = None
            
            request.session['questions'] = qs
            
            try:
                correct_count = int(question.get('correct_count'))
            except (TypeError, ValueError):
                correct_count = -1
            
            db_qids = request.session.get('db_question_ids') or []
            if isinstance(db_qids, list) and idx < len(db_qids):
                given = qs[idx]['given_answer']
                is_corr = bool(given is not None and int(given) == correct_count)
                TestQuestion.objects.filter(id=db_qids[idx]).update(
                    student_response=str(given if given is not None else ''),
                    is_correct=is_corr
                )
            
            try:
                ans_val = int(ans) if ans and ans.isdigit() else None
            except Exception:
                ans_val = None
            
            if selected_type == 'similar_on_pages':
                correct_count_val = correct_count
                request.session['pages_flow'] = {'q_index': idx, 'target_total': correct_count_val, 'current': 1}
                _flow_set_total(request, correct_count_val)
                return redirect('core:pages_choose_juz')
            
            if ans and ans.isdigit() and int(ans) == correct_count:
                request.session['score'] = request.session.get('score', 0) + 1
            
            request.session['test_index'] = idx + 1
            # التحقق من نوع الاختبار وتوجيه للمسار المناسب
            selected_type = request.session.get('selected_test_type', 'similar_count')
            if selected_type == 'similar_count':
                return redirect('tests:similar_count:question')
            elif selected_type == 'similar_on_pages':
                return redirect('tests:similar_on_pages:question')
            elif selected_type == 'verse_location_quarters':
                return redirect('tests:verse_location_quarters:question')
            else:
                return redirect('core:test_question')
    selected_type = request.session.get('selected_test_type', 'similar_count')
    
    if selected_type == 'verse_location_quarters':
        # عرض سؤال موقع الآية
        question = qs[idx]
        stage = question.get('stage', 'quarter_selection')
        # If page feedback is pending, render it immediately
        if question.get('show_feedback') and question.get('feedback_stage') == 'page':
            correct_page_in_quarter = question.get('correct_page_in_quarter', 1)
            page_answer = question.get('page_answer')
            page_is_correct = question.get('page_is_correct', False)
            context = {
                'student': student,
                'question_number': idx + 1,
                'total_questions': total,
                'ayah_text': question.get('ayah_text', ''),
                'correct_page_in_quarter': correct_page_in_quarter,
                'page_answer': page_answer,
                'page_is_correct': page_is_correct,
                'scope_label': request.session.get('scope_label', ''),
                'progress_percent': progress,
                'question_type': 'verse_location_quarters',
                'stage': 'page_feedback',
                'submitted': False,
                'hide_footer': True
            }
            return render(request, 'core/verse_location_question.html', context)
        
        # التحقق من وجود تحقق فوري
        if question.get('show_feedback') and question.get('feedback_stage') == 'quarter':
            # عرض التحقق من الربع
            correct_quarter = question.get('correct_quarter', '')
            quarter_answer = question.get('quarter_answer')
            quarter_is_correct = question.get('quarter_is_correct', False)
            
            context = {
                'student': student,
                'question_number': idx + 1,
                'total_questions': total,
                'ayah_text': question.get('ayah_text', ''),
                'correct_quarter': correct_quarter,
                'quarter_answer': quarter_answer,
                'quarter_is_correct': quarter_is_correct,
                'scope_label': request.session.get('scope_label', ''),
                'progress_percent': progress,
                'question_type': 'verse_location_quarters',
                'stage': 'quarter_feedback',
                'submitted': False,
                'hide_footer': True
            }
            
            return render(request, 'core/verse_location_question.html', context)

        # التحقق من المرحلة الحالية
        if stage == 'page_selection':
            # المرحلة الثانية: اختيار الصفحة داخل الربع
            ayah_text = question.get('ayah_text', '')
            correct_quarter = question.get('correct_quarter', '')
            page_in_quarter_options = question.get('page_in_quarter_options', [])
            
            context = {
                'student': student,
                'question_number': idx + 1,
                'total_questions': total,
                'ayah_text': ayah_text,
                'correct_quarter': correct_quarter,
                'page_in_quarter_options': page_in_quarter_options,
                'scope_label': request.session.get('scope_label', ''),
                'progress_percent': progress,
                'question_type': 'verse_location_quarters',
                'stage': 'page_selection',
                'submitted': False,
                'hide_footer': True
            }
            
            return render(request, 'core/verse_location_question.html', context)
        else:
            # Fallback: render quarter selection screen
            ayah_text = question.get('ayah_text', '')
            quarter_options = question.get('quarter_options', [])
            context = {
                'student': student,
                'question_number': idx + 1,
                'total_questions': total,
                'ayah_text': ayah_text,
                'quarter_options': quarter_options,
                'scope_label': request.session.get('scope_label', ''),
                'progress_percent': progress,
                'question_type': 'verse_location_quarters',
                'stage': 'quarter_selection',
                'submitted': False,
                'hide_footer': True
            }
            
            return render(request, 'core/verse_location_question.html', context)
    
    else:
        # عرض أسئلة موقع الآية
        if selected_type == 'verse_location_quarters':
            # تسجيل للتشخيص
            print(f"🔍 DEBUG: عرض أسئلة موقع الآية")
            print(f"🔍 question: {question}")
            print(f"🔍 ayah_text: {question.get('ayah_text', '')}")
            print(f"🔍 quarter_options: {question.get('quarter_options', [])}")
            print(f"🔍 page_in_quarter_options: {question.get('page_in_quarter_options', [])}")
            
            # عرض مرحلة الاختيار المشترك
            context = {
                'student': student,
                'question_number': idx + 1,
                'total_questions': total,
                'ayah_text': question.get('ayah_text', ''),
                'quarter_options': question.get('quarter_options', []),
                'page_in_quarter_options': question.get('page_in_quarter_options', []),
                'scope_label': request.session.get('scope_label', ''),
                'progress_percent': progress,
                'question_type': 'verse_location_quarters',
                'stage': 'combined_selection',
                'submitted': False,
                'hide_footer': True
            }
            return render(request, 'core/verse_location_question.html', context)
        
        # عرض الأسئلة التقليدية
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
        
        context = {
            'student': student,
            'question_number': idx + 1,
            'total_questions': total,
            'phrase': phrase_txt,
            'options': options,
            'scope_label': request.session.get('scope_label', ''),
            'progress_percent': progress,
            'correct_count': correct_count,
            'submitted': False,
            'hide_footer': True
        }
        
        return render(request, 'core/test_question.html', context)

@user_passes_test(lambda u:u.is_staff)
@login_required
def admin_complaints(request):
    comps=Complaint.objects.select_related('student__user').order_by('-created_at')
    if request.method=='POST':
        cid=request.POST.get('complaint_id'); action=request.POST.get('action')
        try:
            c=Complaint.objects.get(id=cid)
            if action=='toggle': 
                c.resolved=not c.resolved
                c.save()
                status = "تم حلها" if c.resolved else "غير محلولة"
                messages.success(request,f"✅ تم تحديث حالة الشكوى #{cid} إلى: {status}")
        except Complaint.DoesNotExist: messages.error(request,"الشكوى غير موجودة.")
    return render(request,'core/complaint_admin.html',{'complaints':comps,'hide_footer':False})

@login_required
@require_POST
def report_question(request):
    # الحصول على الطالب من المستخدم المسجل
    from core.services.user_service import UserService
    user_service = UserService()
    student = user_service.get_or_create_student(request.user)
    text=(request.POST.get('text','') or '').strip() or '(بدون وصف)'; phrase=(request.POST.get('phrase','') or '').strip(); q_no=request.POST.get('question_number','?'); given=request.POST.get('given','—'); correct=request.POST.get('correct','—'); src=request.POST.get('from','test')
    body=f"[إبلاغ سؤال — المصدر: {src}] سؤال رقم: {q_no} | العبارة: \"{phrase}\" | إجابة الطالب: {given} | الصحيحة: {correct}\nوصف المشكلة: {text}"
    Complaint.objects.create(student=student,text=body)
    if request.headers.get('x-requested-with')=='XMLHttpRequest': return JsonResponse({"ok":True,"message":"🚨 تم إرسال الإبلاغ بنجاح. شكراً لك على مساعدتنا!"})
    return render(request,'core/report_done.html',{'hide_footer':True})

 

def _user_stats(student:Student):
    # نعتمد فقط على الجلسات المكتملة ونستبعد الأسئلة غير المُجابة من الصحيح/الخطأ
    qs=TestQuestion.objects.filter(session__student=student, session__completed=True)
    total_qs=qs.count()
    answered_qs=qs.exclude(student_response='').exclude(student_response__isnull=True)
    answered=answered_qs.count()
    correct=answered_qs.filter(is_correct=True).count()
    wrong=answered_qs.filter(is_correct=False).count()
    unanswered=max(0,total_qs-answered)
    exams=TestSession.objects.filter(student=student,completed=True).count()
    return {'exams':exams,'correct':correct,'wrong':wrong,'unanswered':unanswered}

# Stats views moved to stats_app

# API views moved to api_v1

@login_required
def quarter_pages_view(request,qid:int):
    pg_nums=Ayah.objects.filter(quarter_id=qid,page__isnull=False).values_list('page__number',flat=True); pg_nums=sorted(set(pg for pg in pg_nums if pg is not None))
    pages=Page.objects.filter(number__in=pg_nums).order_by('number')
    return render(request,'core/quarter_pages.html',{'qid':qid,'pages':pages,'hide_footer':True})

def page_svg(request,pno:int):
    candidates=[f"{pno}.svg",f"{pno:02d}.svg",f"{pno:03d}.svg"]; base=os.path.join(settings.MEDIA_ROOT,'pages')
    for fname in candidates:
        path=os.path.join(base,fname)
        if os.path.exists(path) and os.path.getsize(path)>0: return FileResponse(open(path,'rb'),content_type='image/svg+xml')
    raise Http404("Page SVG not found")

@login_required
def pages_quarter_pick(request,qid:int):
    sid=request.session.get('student_id'); student=get_object_or_404(Student,id=sid)
    qobj=get_object_or_404(Quarter,id=qid); juz_no_for_q=qobj.juz.number
    question,flow=_current_question_and_flow(request); feedback=None; delta=None
    if question:
        expected=int((request.session.get(_ns(request,'pages_flow')) or {}).get('current',1))
        occ_ids=question.get('occurrence_ayah_ids',[]) or []
        ay_quarters=list(Ayah.objects.filter(id__in=occ_ids).order_by('surah','number').values_list('id','quarter_id'))
        idx_to_qid={i:q for i,(_,q) in enumerate(ay_quarters,start=1)}; expected_qid=idx_to_qid.get(expected)
        # التحقق من ترتيب المواضع
        position_order = request.session.get('position_order', 'normal')
        
        if expected_qid==qid:
            # الربع صحيح للموضع الحالي
            cfg=_pages_cfg_get(request); per_pos=cfg['per_pos']; score_now,delta=_grade_push(request,f"إتمام موضع {ar_ordinal(expected)}",+per_pos)
            flow=_flow_mark_completed(request)
            
            # حفظ معلومات الموضع المكتمل
            if 'completed_positions_details' not in request.session:
                request.session['completed_positions_details'] = {}
            
            request.session['completed_positions_details'][str(expected)] = {
                'juz_no': juz_no_for_q,
                'quarter_id': qid,
                'quarter_index': qobj.index_in_juz,
                'score': per_pos
            }
            
            # إذا كان هناك مواضع أخرى، نذهب لصفحة القرآن
            if flow.get('current', 1) <= flow.get('total', 1):
                return redirect('core:pages_quarter_viewer', qid=qid)
            else:
                # انتهت جميع المواضع، نذهب للسؤال التالي
                return redirect('core:pages_choose_juz')
        else:
            picked_index=next((i for i,q in idx_to_qid.items() if q==qid),None)
            if picked_index:
                if position_order == 'sequential':
                    # إذا كان الترتيب إجباري، لا نسمح باختيار موضع آخر
                    score_now,delta=_grade_push(request,"الترتيب إجباري - يجب اختيار الموضع الحالي",-PENALTY_WRONG_QUARTER_OTHER)
                    feedback=_feedback('error',f"الترتيب إجباري! يجب أن تختار الربع الخاص بالموضع {ar_ordinal(expected)} أولاً. {delta}%−")
                    # إعادة توجيه لاختيار الربع الصحيح
                    quarters=Quarter.objects.filter(juz__number=juz_no_for_q).order_by('index_in_juz')
                    ctx={'student':student,'juz_no':juz_no_for_q,'quarters':quarters,'hide_footer':True,'disabled_quarters':[]}
                    score_now2,st=_grade_get(request)
                    ctx.update({'gauge_score':score_now2,'gauge_events':(st.get('events') or [])[:6],'flow_total':flow.get('total'),'flow_current':flow.get('current'),'flow_completed':flow.get('completed',[])})
                    return render(request,'core/pages_choose_quarter.html',_ctx_common(request,ctx,feedback,delta))
                else:
                    # إذا كان الترتيب غير إجباري، نسمح باختيار موضع آخر
                    flow['current']=picked_index; request.session['pages_flow']=flow
                    score_now,delta=_grade_push(request,"اختيار ربع يخص موضع آخر",-PENALTY_WRONG_QUARTER_OTHER)
                    feedback=_feedback('warning',f"الربع المختار يخص الموضع {ar_ordinal(picked_index)} وليس {ar_ordinal(expected)}. سنكمل على هذا الموضع. {delta}%−")
            else:
                score_now,delta=_grade_push(request,"لا يوجد أي موضع في هذا الربع",-PENALTY_EMPTY_QUARTER)
                flow=request.session.get('pages_flow') or {}; current_step=int((flow or {}).get('current') or 1)
                dis=(flow.setdefault('disabled',{}).setdefault(f"step_{current_step}",{'juz':[],'q':[]}))
                if qid not in dis['q']: dis['q'].append(qid)
                request.session['pages_flow']=flow
                quarters=Quarter.objects.filter(juz__number=juz_no_for_q).order_by('index_in_juz')
                ctx={'student':student,'juz_no':juz_no_for_q,'quarters':quarters,'hide_footer':True,'disabled_quarters':dis['q']}
                score_now2,st=_grade_get(request)
                ctx.update({'gauge_score':score_now2,'gauge_events':(st.get('events') or [])[:6],'flow_total':flow.get('total'),'flow_current':flow.get('current'),'flow_completed':flow.get('completed',[])})
                fb=_feedback('error',f"لا يوجد أي موضع في هذا الربع. {delta}%−"); return render(request,'core/pages_choose_quarter.html',_ctx_common(request,ctx,fb,delta))
    pg_nums=Ayah.objects.filter(quarter_id=qid,page__isnull=False).values_list('page__number',flat=True); pg_nums=sorted(set(pg for pg in pg_nums if pg is not None))
    pages=Page.objects.filter(number__in=pg_nums).order_by('number')
    
    # معلومات الربع
    quarter_info = {
        'juz_no': qobj.juz.number,
        'quarter_index': qobj.index_in_juz,
        'quarter_name': None
    }
    
    # الحصول على اسم الربع (أول آية)
    try:
        first_ayah = Ayah.objects.filter(quarter=qobj).order_by('surah', 'number').first()
        if first_ayah:
            quarter_info['quarter_name'] = first_ayah.text[:25] + "..." if len(first_ayah.text) > 25 else first_ayah.text
    except:
        pass
    
    # معلومات العبارة الحالية
    current_phrase = ''
    if question:
        current_phrase = question.get('phrase_text') or question.get('phrase') or ''
    
    # معلومات المواضع
    positions_info = None
    if question and flow:
        total_positions = flow.get('total', 0)
        current_position = flow.get('current', 1)
        completed_positions = flow.get('completed', [])
        
        if total_positions > 0:
            positions = []
            for i in range(1, total_positions + 1):
                positions.append({
                    'completed': i in completed_positions,
                    'current': i == current_position
                })
            
            positions_info = {
                'total': total_positions,
                'positions': positions
            }
    
    ctx={
        'qid': qid,
        'pages': pages,
        'quarter_info': quarter_info,
        'current_phrase': current_phrase,
        'positions_info': positions_info,
        'hide_footer': True
    }
    
    return render(request,'core/quarter_pages.html',_ctx_common(request,ctx,feedback,delta))

# api_pages_select_first moved to api_v1

@login_required
def pages_quarter_viewer(request,qid:int):
    sid=request.session.get('student_id'); student=get_object_or_404(Student,id=sid)
    qobj=get_object_or_404(Quarter,id=qid)
    
    # الحصول على السؤال الحالي والعبارة
    question, flow = _current_question_and_flow(request)
    
    pg_nums=Ayah.objects.filter(quarter_id=qid,page__isnull=False).values_list('page__number',flat=True); pages=sorted(set(p for p in pg_nums if p is not None))
    if not pages:
        # هذا الربع لا يحتوي على صفحات
        score_now,delta=_grade_push(request,"اختيار ربع خاطئ - لا يحتوي على صفحات",-PENALTY_WRONG_QUARTER_OTHER)
        
        # إضافة الربع للقائمة المحظورة
        if 'disabled_quarters' not in request.session:
            request.session['disabled_quarters'] = []
        if qid not in request.session['disabled_quarters']:
            request.session['disabled_quarters'].append(qid)
        
        # الحصول على رقم الجزء
        quarters=Quarter.objects.filter(id=qid).select_related('juz'); juz_no=quarters[0].juz.number if quarters else None
        if juz_no:
            # إعادة توجيه لصفحة اختيار الربع مع رسالة خطأ
            ctx={'student':student,'juz_no':juz_no,'quarters':Quarter.objects.filter(juz__number=juz_no).order_by('index_in_juz'),'hide_footer':True,'disabled_quarters':request.session.get('disabled_quarters', [])}
            fb=_feedback('error',f"اختيارك غلط! هذا الربع مفيش فيه صفحات. {delta}%−")
            return render(request,'core/pages_choose_quarter.html',_ctx_common(request,ctx,fb,delta))
        return redirect('core:pages_choose_juz')
    
    spreads=[]; i=0
    while i<len(pages):
        left=pages[i]; right=pages[i+1] if i+1<len(pages) else None; spreads.append((left,right)); i+=2
    
    # معلومات الربع
    quarter_info = {
        'juz_no': qobj.juz.number,
        'quarter_index': qobj.index_in_juz,
        'quarter_name': None
    }
    
    # الحصول على اسم الربع (أول آية)
    try:
        first_ayah = Ayah.objects.filter(quarter=qobj).order_by('surah', 'number').first()
        if first_ayah:
            quarter_info['quarter_name'] = first_ayah.text[:25] + "..." if len(first_ayah.text) > 25 else first_ayah.text
    except:
        pass
    
    # معلومات العبارة الحالية
    current_phrase = ''
    if question:
        current_phrase = question.get('phrase_text') or question.get('phrase') or ''
    
    # معلومات المواضع
    positions_info = None
    if question and flow:
        total_positions = flow.get('total', 0)
        current_position = flow.get('current', 1)
        completed_positions = flow.get('completed', [])
        
        if total_positions > 0:
            positions = []
            for i in range(1, total_positions + 1):
                positions.append({
                    'completed': i in completed_positions,
                    'current': i == current_position
                })
            
            positions_info = {
                'total': total_positions,
                'positions': positions
            }
    
    ctx={
        'qid': qid,
        'spreads': spreads,
        'first_pair': spreads[0],
        'quarter_info': quarter_info,
        'current_phrase': current_phrase,
        'positions_info': positions_info,
        'hide_footer': True
    }
    
    return render(request,'core/quarter_viewer.html',_ctx_common(request,ctx))

@login_required
def pages_choose_juz(request):
    sid=request.session.get('student_id'); student=get_object_or_404(Student,id=sid)
    cfg=_pages_cfg_get(request); flow=_flow_get(request)
    if request.headers.get('x-requested-with')=='XMLHttpRequest' and request.GET.get('ajax'):
        if request.GET.get('order')=='1':
            score_now,_=_grade_mark_order(request); request.session['pages_order']=True; ev={'t':"اختيار بالترتيب (Bonus)",'d':PAGES_BONUS_ORDER}
            return JsonResponse({'ok':True,'gauge_score':score_now,'event':ev,'order_mode':True})
        if request.GET.get('set_n'):
            try: n=int(request.GET.get('set_n'))
            except Exception: n=cfg['total']
            cfg,flow=_flow_set_total(request,n); ev={'t':f"تعيين عدد المواضع إلى {cfg['total']}",'d':0}
            return JsonResponse({'ok':True,'flow':flow,'cfg':cfg,'event':ev})
        return JsonResponse({'ok':False},status=400)
    
    # الحصول على السؤال الحالي والعبارة
    question, flow = _current_question_and_flow(request)
    current_phrase = ''
    if question:
        current_phrase = question.get('phrase_text') or question.get('phrase') or ''
    
    allowed_juz_numbers=_allowed_juz_numbers_for_scope(request)
    
    # الحصول على أسماء الأجزاء
    juz_names = {}
    juz_with_positions = []
    
    for juz_no in allowed_juz_numbers:
        try:
            # البحث عن أول آية في الجزء
            first_ayah = Ayah.objects.filter(quarter__juz__number=juz_no).order_by('surah', 'number').first()
            if first_ayah:
                juz_names[juz_no] = first_ayah.text[:30] + "..." if len(first_ayah.text) > 30 else first_ayah.text
            else:
                juz_names[juz_no] = f"الجزء {juz_no}"
        except:
            juz_names[juz_no] = f"الجزء {juz_no}"
    
    # معلومات المواضع
    positions_info = None
    if question and flow:
        total_positions = flow.get('total', 0)
        current_position = flow.get('current', 1)
        completed_positions = flow.get('completed', [])
        
        if total_positions > 0:
            positions = []
            for i in range(1, total_positions + 1):
                positions.append({
                    'completed': i in completed_positions,
                    'current': i == current_position
                })
            
            positions_info = {
                'total': total_positions,
                'positions': positions
            }
    
    # الحصول على الأجزاء المحظورة
    disabled_juz = request.session.get('disabled_juz', [])
    
    context={
        'student': student,
        'juz_numbers': allowed_juz_numbers,
        'juz_names': juz_names,
        'current_phrase': current_phrase,
        'positions_info': positions_info,
        'disabled_juz': disabled_juz,
        'had_scope': bool(request.session.get('selected_quarters') or request.session.get('selected_juz')),
        'hide_footer': True
    }
    
    order_param=request.GET.get('order')
    if order_param in ('0','1'):
        if order_param=='1': _grade_mark_order(request); request.session['pages_order']=True
        else: request.session['pages_order']=False
    if not allowed_juz_numbers:
        reason=[]
        if request.session.get('selected_quarters') or request.session.get('selected_juz'): reason.append("النطاق الذي اخترته لا يحتوي على أرباع بها صفحات.")
        else: reason.append("لا توجد صفحات مرتبطة بالأرباع حتى الآن.")
        context['no_juz_reason']=" ".join(reason)
    
    # إضافة رسالة التحذير إذا كان هناك أجزاء محظورة
    if request.session.get('disabled_juz'):
        context['disabled_juz_message'] = "تم إغلاق بعض الأجزاء لعدم احتوائها على مواضع مطلوبة"
        context['show_disabled_warning'] = True
    
    score_now,st=_grade_get(request)
    context.update({'gauge_score':score_now,'gauge_events':(st.get('events') or [])[:6],'order_mode':bool(request.session.get('pages_order')),'flow_total':flow.get('total'),'flow_current':flow.get('current'),'flow_completed':flow.get('completed',[]),'n_options':list(range(1,11))})
    return render(request,'core/pages_choose_juz.html',_ctx_common(request,context))

@login_required
def pages_quarter_pick_redirect(request, qid: int):
    """توجيه صفحة quarter مباشرة لصفحة اختيار الربع"""
    # الحصول على رقم الجزء من الربع
    try:
        quarter = Quarter.objects.get(id=qid)
        juz_no = quarter.juz.number
        return redirect('core:pages_choose_quarter', juz_no=juz_no)
    except Quarter.DoesNotExist:
        return redirect('core:pages_choose_juz')

@login_required
def pages_choose_quarter(request,juz_no:int):
    sid=request.session.get('student_id'); student=get_object_or_404(Student,id=sid)
    question,flow=_current_question_and_flow(request); feedback=None; delta=None
    
    # Debug info
    # print(f"=== DEBUG: pages_choose_quarter ===")
    # print(f"question: {question}")
    # print(f"flow: {flow}")
    # print(f"juz_no: {juz_no}")
    
    # معالجة اختيار الربع
    if request.method == 'POST':
        quarter_id = request.POST.get('quarter_id')
        if quarter_id:
            try:
                quarter = Quarter.objects.get(id=quarter_id)
                
                # التحقق من أن الربع يحتوي على الموضع المطلوب
                if question and flow:
                    expected_position = int(flow.get('current', 1))
                    occ_ids = question.get('occurrence_ayah_ids', []) or []
                    
                    # البحث عن المواضع في هذا الربع
                    quarter_positions = []
                    
                    for i, ayah_id in enumerate(occ_ids, 1):
                        try:
                            ayah = Ayah.objects.get(id=ayah_id)
                            if ayah.quarter.id == quarter.id:
                                quarter_positions.append(i)
                        except Ayah.DoesNotExist:
                            continue
                    
                    # إذا كان الربع يحتوي على الموضع المطلوب
                    if expected_position in quarter_positions:
                        # التوجيه لصفحة الربع
                        return redirect('core:pages_quarter_viewer', qid=quarter.id)
                    else:
                        # هذا الربع لا يحتوي على الموضع المطلوب
                        score_now, delta = _grade_push(request, "اختيار ربع خاطئ - لا يحتوي على الموضع المطلوب", -PENALTY_WRONG_QUARTER_OTHER)
                        
                        # إضافة الربع للقائمة المحظورة
                        if 'disabled_quarters' not in request.session:
                            request.session['disabled_quarters'] = []
                        if quarter.id not in request.session['disabled_quarters']:
                            request.session['disabled_quarters'].append(quarter.id)
                        
                        feedback = _feedback('error', f"اختيارك غلط! هذا الربع مفيش فيه الموضع المطلوب. {delta}%−")
                        delta = delta
                else:
                    # لا يوجد سؤال حالي، السماح بالدخول
                    return redirect('core:pages_quarter_viewer', qid=quarter.id)
                    
            except Quarter.DoesNotExist:
                feedback = _feedback('error', "الربع المختار غير موجود")
                delta = None
    
    # الحصول على العبارة الحالية
    current_phrase = ''
    if question:
        current_phrase = question.get('phrase_text') or question.get('phrase') or ''
    
    quarters=Quarter.objects.filter(juz__number=juz_no).order_by('index_in_juz')
    
    # الحصول على الأرباع المحظورة
    disabled_quarters = request.session.get('disabled_quarters', [])
    
    # الحصول على أسماء الأرباع
    quarter_names = {}
    for quarter in quarters:
        try:
            # البحث عن أول آية في الربع
            first_ayah = Ayah.objects.filter(quarter=quarter).order_by('surah', 'number').first()
            if first_ayah:
                quarter_names[quarter.id] = first_ayah.text[:25] + "..." if len(first_ayah.text) > 25 else first_ayah.text
            else:
                quarter_names[quarter.id] = f"الربع {quarter.index_in_juz}"
        except:
            quarter_names[quarter.id] = f"الربع {quarter.index_in_juz}"
    
    if question:
        expected=int((request.session.get('pages_flow') or {}).get('current',1))
        occ_ids=question.get('occurrence_ayah_ids',[]) or []
        ay_juzs=Ayah.objects.filter(id__in=occ_ids).order_by('surah','number').values_list('id','quarter__juz__number')
        idx_to_juz={i:j for i,(_,j) in enumerate(ay_juzs,start=1)}; expected_juz=idx_to_juz.get(expected)
        # التحقق من ترتيب المواضع
        position_order = request.session.get('position_order', 'normal')
        
        if expected_juz is not None:
            if juz_no==expected_juz: 
                feedback=None; delta=None
            else:
                picked_index=next((i for i,j in idx_to_juz.items() if j==juz_no),None)
                if picked_index:
                    if position_order == 'sequential':
                        # إذا كان الترتيب إجباري، لا نسمح باختيار موضع آخر
                        score_now,delta=_grade_push(request,"الترتيب إجباري - يجب اختيار الموضع الحالي",-PENALTY_WRONG_JUZ_OTHER)
                        feedback=_feedback('error',f"الترتيب إجباري! يجب أن تختار الجزء الخاص بالموضع {ar_ordinal(expected)} أولاً. {delta}%−")
                    else:
                        # إذا كان الترتيب غير إجباري، نسمح باختيار موضع آخر
                        flow['current']=picked_index; request.session['pages_flow']=flow
                        score_now,delta=_grade_push(request,"اختيار جزء يخص موضع آخر",-PENALTY_WRONG_JUZ_OTHER)
                        feedback=_feedback('warning',f"الجزء المختار يخص الموضع {ar_ordinal(picked_index)} وليس {ar_ordinal(expected)}. سنكمل على هذا الموضع. {delta}%−")
                else:
                    # هذا الجزء لا يحتوي على أي مواضع مطلوبة
                    score_now,delta=_grade_push(request,"اختيار جزء خاطئ - لا يحتوي على مواضع",-PENALTY_WRONG_JUZ_OTHER)
                    feedback=_feedback('error',f"اختيارك غلط! الجزء {juz_no} مفيش فيه أي مواضع من المواضع المطلوبة. {delta}%−")
                    
                    # إضافة الجزء للقائمة المحظورة
                    if 'disabled_juz' not in request.session:
                        request.session['disabled_juz'] = []
                    if juz_no not in request.session['disabled_juz']:
                        request.session['disabled_juz'].append(juz_no)
                    
                    # إعادة توجيه لصفحة اختيار الجزء مع رسالة
                    return redirect('core:pages_choose_juz')
    # معلومات المواضع
    positions_info = None
    if question and flow:
        total_positions = flow.get('total', 0)
        current_position = flow.get('current', 1)
        completed_positions = flow.get('completed', [])
        
        if total_positions > 0:
            positions = []
            for i in range(1, total_positions + 1):
                positions.append({
                    'completed': i in completed_positions,
                    'current': i == current_position
                })
            
            positions_info = {
                'total': total_positions,
                'positions': positions
            }
    
    ctx={
        'student': student,
        'juz_no': juz_no,
        'quarters': quarters,
        'quarter_names': quarter_names,
        'current_phrase': current_phrase,
        'positions_info': positions_info,
        'disabled_quarters': disabled_quarters,
        'hide_footer': True
    }
    score_now,st=_grade_get(request)
    ctx.update({'gauge_score':score_now,'gauge_events':(st.get('events') or [])[:6],'flow_total':flow.get('total'),'flow_current':flow.get('current'),'flow_completed':flow.get('completed',[])})
    return render(request,'core/pages_choose_quarter.html',_ctx_common(request,ctx,feedback,delta))

def _pages_cfg_get(request):
    cfg=request.session.get('pages_cfg') or {}; total=int(cfg.get('total') or 3); per_pos=cfg.get('per_pos')
    if not per_pos: per_pos=round(100/max(1,total),2)
    cfg['total']=total; cfg['per_pos']=per_pos; request.session['pages_cfg']=cfg; return cfg

def _flow_get(request):
    flow=request.session.get('pages_flow') or {}; flow.setdefault('current',1); flow.setdefault('completed',[])
    cfg=_pages_cfg_get(request); flow['total']=cfg['total']; request.session['pages_flow']=flow; return flow

def _flow_set_total(request,n:int):
    cfg=_pages_cfg_get(request); n=max(1,min(50,int(n))); cfg['total']=n; cfg['per_pos']=round(100/n,2); request.session['pages_cfg']=cfg
    flow=_flow_get(request); flow['total']=n; flow['current']=min(flow.get('current',1),n); flow['completed']=[i for i in flow.get('completed',[]) if 1<=int(i)<=n]; request.session['pages_flow']=flow
    
    # مسح الأجزاء والأرباع المحظورة عند بداية اختبار جديد
    if 'disabled_juz' in request.session:
        del request.session['disabled_juz']
    if 'disabled_quarters' in request.session:
        del request.session['disabled_quarters']
    
    return cfg,flow

def _flow_mark_completed(request):
    flow=_flow_get(request); cur=int(flow.get('current',1))
    if cur not in flow['completed']: flow['completed']=list(flow['completed'])+[cur]
    if cur<int(flow.get('total',1)): flow['current']=cur+1
    request.session['pages_flow']=flow; return flow

def _ns(request,base:str)->str:
    sid=request.session.get('db_session_id'); return f"{base}:{sid}" if sid else base

@login_required
def test_next(request):
    tid=request.session.get('db_session_id'); ns=_ns(request,f'flow:{tid}')
    flow=request.session.get(ns) or {'current':1,'total':0}
    flow['current']=min(int(flow.get('current',1))+1,int(flow.get('total',0)) or 1)
    request.session[ns]=flow; request.session.modified=True
    return redirect('core:test_question')

@login_required
def test_prev(request):
    tid=request.session.get('db_session_id'); ns=_ns(request,f'flow:{tid}')
    flow=request.session.get(ns) or {'current':1,'total':0}
    flow['current']=max(int(flow.get('current',1))-1,1)
    request.session[ns]=flow; request.session.modified=True
    return redirect('core:test_question')

class FlowSmokeTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.u = User.objects.create_user(username='u', password='p')
        self.client.login(username='u', password='p')
        s = self.client.session
        # مبدئياً: امتحان عدّ المواضع
        s['student_id'] = 1
        s['selected_test_type'] = 'similar_count'
        s['selected_juz'] = [1]
        s['num_questions'] = 5
        s['difficulty'] = 'mixed'
        s.save()

    def test_start_initializes_flow(self):
        r = self.client.get(reverse('core:start_test'))
        self.assertEqual(r.status_code, 302)
        s = self.client.session
        tid = s.get('db_session_id')
        self.assertIsNotNone(tid)
        flow = s.get(f'flow:{tid}') or {}
        self.assertEqual(flow.get('current'), 1)
        self.assertGreaterEqual(int(flow.get('total', 0)), 1)

    def test_progress_pct_zero_at_start(self):
        # دي بتقيس كون التقدّم صفر في أول سؤال (لو القالب بيرجّع context)
        self.client.get(reverse('core:start_test'))
        resp = self.client.get(reverse('core:test_question'))
        ctx = getattr(resp, 'context', None)
        # الاختبار ده مرتبط بالتقدّم الداخلي للامتحان الآخر (pages)،
        # لو مش محتاجه هنا ممكن تعلّقه أو تخصص سيناريو similar_on_pages.
        if ctx is not None:
            self.assertIn('progress_pct', ctx)
            self.assertEqual(ctx['progress_pct'], 0)

@login_required
def pages_show_positions(request):
    """عرض المواضع بشكل منظم"""
    sid = request.session.get('student_id')
    student = get_object_or_404(Student, id=sid)
    
    # الحصول على السؤال الحالي والفلو
    question, flow = _current_question_and_flow(request)
    
    if not question:
        messages.error(request, "لا يوجد سؤال حالي")
        return redirect('core:main_menu')
    
    # الحصول على عدد المواضع من السؤال
    total_positions = len(question.get('occurrence_ayah_ids', []) or [])
    
    if total_positions == 0:
        messages.error(request, "لا توجد مواضع متاحة")
        return redirect('core:main_menu')
    
    # إنشاء قائمة المواضع
    positions = []
    for i in range(1, total_positions + 1):
        positions.append({
            'number': i,
            'arabic_number': ar_ordinal(i),
            'is_current': i == flow.get('current', 1),
            'is_completed': i in flow.get('completed', []),
            'status': 'current' if i == flow.get('current', 1) else ('completed' if i in flow.get('completed', []) else 'pending')
        })
    
    context = {
        'student': student,
        'question': question,
        'positions': positions,
        'total_positions': total_positions,
        'current_position': flow.get('current', 1),
        'hide_footer': True
    }
    
    return render(request, 'core/pages_show_positions.html', _ctx_common(request, context))

# =========================
# Similar on pages: دوال إضافية
# =========================

@login_required
def pages_choose_juz(request):
    """اختيار الجزء لاختبار مواضع المتشابهات في الصفحات"""
    sid = request.session.get('student_id')
    student = get_object_or_404(Student, id=sid)
    
    # إعدادات وعدّاد التقدم
    cfg = _pages_cfg_get(request)
    flow = _flow_get(request)
    
    # AJAX: تفعيل البونص أو تعيين عدد المواضع بدون تنقّل
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.GET.get('ajax'):
        # تفعيل "بالترتيب" كبونص فقط
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
    
    # fallback قديم: دعم ?order=1/0 لو اتبعت كرابط
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
    
    # اجمع قائمة الأجزاء المقفولة في نفس الموضع
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
        'n_options': list(range(1, 11)),
    })
    
    return render(request, 'core/pages_choose_juz.html', _ctx_common(request, context))


@login_required
def pages_choose_quarter(request, juz_no: int):
    """اختيار الربع لاختبار مواضع المتشابهات في الصفحات"""
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
                .order_by('surah', 'number')
                .values_list('id', 'quarter__juz__number')
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


@login_required
def pages_quarter_pick(request, qid: int):
    """اختيار الربع المحدد لاختبار مواضع المتشابهات في الصفحات"""
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
                .order_by('surah', 'number')
                .values_list('id', 'quarter_id')
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

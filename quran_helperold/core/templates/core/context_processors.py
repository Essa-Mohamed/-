from .models import Student, TestSession, TestQuestion

def _score_formula(exams, correct, wrong, unanswered):
    base = correct - 0.6*wrong - 0.2*unanswered
    acc  = (correct/(correct+wrong)) if (correct+wrong) else 0.0
    volume_bonus = min(exams, 30)*2
    return max(0, base + 40*acc + volume_bonus)

def inject_student(request):
    ctx = {}
    if request.user.is_authenticated:
        student, _ = Student.objects.get_or_create(
            user=request.user, defaults={'display_name': request.user.username}
        )
        ctx['student'] = student

        # احسب ترتيب بسيط (نحتاجه للبادج فقط)
        sess_qs = TestSession.objects.filter(student=student)
        exams = sess_qs.count()
        if exams >= 1:
            ans_qs = TestQuestion.objects.filter(session__in=sess_qs)
            correct = ans_qs.filter(is_correct=True).count()
            wrong   = ans_qs.filter(is_correct=False).count()
            unanswered = 0
            for s in sess_qs.only('id','num_questions'):
                answered = TestQuestion.objects.filter(session=s).count()
                unanswered += max(0, (s.num_questions or 0) - answered)
            my_score = _score_formula(exams, correct, wrong, unanswered)

            # رُتبة تقريبية: احسب كم واحد أعلى مني
            higher = 0
            for st in Student.objects.exclude(id=student.id):
                qs = TestSession.objects.filter(student=st)
                ex = qs.count()
                if ex < 1: 
                    continue
                ans = TestQuestion.objects.filter(session__in=qs)
                c = ans.filter(is_correct=True).count()
                w = ans.filter(is_correct=False).count()
                un = 0
                for s in qs.only('id','num_questions'):
                    a = TestQuestion.objects.filter(session=s).count()
                    un += max(0, (s.num_questions or 0) - a)
                sc = _score_formula(ex, c, w, un)
                if sc > my_score:
                    higher += 1
                    if higher >= 3:  # نحتاج فقط نعرف هل ضمن الثلاثة الأوائل
                        break
            ctx['my_rank'] = higher + 1  # 1..N (تقريبي لكنه كافي للبادج)
    return ctx

from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, DetailView, FormView
from django.contrib import messages

from core.models import TestSession
from tests_app.services.test_service import TestService
from core.services.user_service import UserService


class SelectionView(LoginRequiredMixin, TemplateView):
    template_name = 'similar_count/selection.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_service = UserService()
        student = user_service.get_or_create_student(self.request.user)
        context['student'] = student
        context['selected_test_type'] = 'similar_count'

        from core.models import Juz, Quarter
        juz_quarters_map = {}
        for juz in Juz.objects.all():
            quarters = Quarter.objects.filter(juz=juz).order_by('index_in_juz')
            juz_quarters_map[juz] = {
                'quarters': quarters,
                'first_label': quarters.first().label if quarters.exists() else ''
            }
        context['juz_quarters_map'] = juz_quarters_map
        context['num_questions_options'] = [5, 10, 15, 20, 25, 30]
        return context


class StartView(LoginRequiredMixin, FormView):
    def post(self, request, *args, **kwargs):
        user_service = UserService()
        student = user_service.get_or_create_student(request.user)

        test_type = 'similar_count'
        selected_juz = request.POST.getlist('selected_juz', [])
        selected_quarters = request.POST.getlist('selected_quarters', [])
        num_questions = int(request.POST.get('num_questions', 10))
        difficulty = request.POST.get('difficulty', 'mixed')
        position_order = request.POST.get('position_order', 'normal')

        test_service = TestService(student)
        session = test_service.create_test_session(
            test_type=test_type,
            selected_juz=[int(j) for j in selected_juz],
            selected_quarters=[int(q) for q in selected_quarters],
            num_questions=num_questions,
            difficulty=difficulty,
            position_order=position_order
        )

        request.session['test_index'] = 0
        return redirect('tests:similar_count:question', session_id=session.id)


class QuestionView(LoginRequiredMixin, DetailView):
    model = TestSession
    template_name = 'similar_count/question.html'
    context_object_name = 'session'
    pk_url_kwarg = 'session_id'

    def get_queryset(self):
        user_service = UserService()
        student = user_service.get_or_create_student(self.request.user)
        return TestSession.objects.filter(student=student)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.get_object()
        current_index = self.request.session.get('test_index', 0)
        questions = list(session.questions.all())
        if current_index < len(questions):
            question = questions[current_index]
            context['question'] = question
            context['current_index'] = current_index
            context['total_questions'] = len(questions)
            context['progress'] = (current_index / len(questions)) * 100
            
            # إنشاء خيارات الإجابة
            correct_answer = int(question.correct_answer) if question.correct_answer else 0
            options = []
            
            # إضافة الإجابة الصحيحة
            options.append(correct_answer)
            
            # إضافة خيارات خاطئة قريبة
            if correct_answer > 0:
                options.append(correct_answer - 1)
            if correct_answer < 10:
                options.append(correct_answer + 1)
            if correct_answer > 1:
                options.append(correct_answer - 2)
            if correct_answer < 9:
                options.append(correct_answer + 2)
            
            # إضافة خيارات عشوائية
            import random
            while len(options) < 6:
                random_option = random.randint(0, 15)
                if random_option not in options:
                    options.append(random_option)
            
            # ترتيب الخيارات عشوائياً
            random.shuffle(options)
            context['options'] = options
            
        return context

    def post(self, request, *args, **kwargs):
        session = self.get_object()
        test_service = TestService(session.student)
        current_index = request.session.get('test_index', 0)
        questions = list(session.questions.all())
        if current_index < len(questions):
            question = questions[current_index]
            answer = request.POST.get('answer', '')
            test_service.submit_answer(question.id, answer)
            request.session['test_index'] = current_index + 1
            if current_index + 1 >= len(questions):
                results = test_service.complete_test_session(session.id)
                request.session['test_results'] = results
                return redirect('tests:similar_count:result')
            else:
                return redirect('tests:similar_count:question', session_id=session.id)
        return redirect('tests:tests_root')


class ResultView(LoginRequiredMixin, TemplateView):
    template_name = 'similar_count/result.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        results = self.request.session.get('test_results', {})
        if not results:
            messages.error(self.request, 'لا توجد نتائج للعرض')
            return context
        context.update(results)
        context['test_type'] = 'similar_count'
        self.request.session.pop('test_results', None)
        self.request.session.pop('test_index', None)
        return context



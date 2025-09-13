from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, DetailView, FormView
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import Http404

from testing.models import TestSession
from tests_app.services.test_service import TestService
from core.services.user_service import UserService


class SelectionView(LoginRequiredMixin, TemplateView):
    template_name = 'core/test_selection.html'
    
    def dispatch(self, request, *args, **kwargs):
        # التحقق من صلاحيات المستخدم
        ALLOWED_EMAIL = "essagamer91@gmail.com"
        if request.user.email != ALLOWED_EMAIL:
            raise Http404("هذه الميزة غير متاحة حالياً. ستكون متاحة قريباً!")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_service = UserService()
        student = user_service.get_or_create_student(self.request.user)
        context['student'] = student
        context['selected_test_type'] = 'similar_on_pages'

        from quran_structure.models import Juz, Quarter
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

        test_type = 'similar_on_pages'
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
        return redirect('tests:similar_on_pages:question', session_id=session.id)


class QuestionView(LoginRequiredMixin, DetailView):
    model = TestSession
    template_name = 'core/test_question.html'
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
            context['question'] = questions[current_index]
            context['current_index'] = current_index
            context['total_questions'] = len(questions)
            context['progress'] = (current_index / len(questions)) * 100
        return context

    def post(self, request, *args, **kwargs):
        session = self.get_object()
        test_service = TestService(session.student)
        current_index = request.session.get('test_index', 0)
        questions = list(session.questions.all())
        if current_index < len(questions):
            question = questions[current_index]
            answer = request.POST.get('answer', '')
            is_correct, message = test_service.submit_answer(question.id, answer)
            request.session['test_index'] = current_index + 1
            if current_index + 1 >= len(questions):
                results = test_service.complete_test_session(session.id)
                request.session['test_results'] = results
                return redirect('tests:similar_on_pages:result')
            else:
                return redirect('tests:similar_on_pages:question', session_id=session.id)
        return redirect('tests:tests_root')


class ResultView(LoginRequiredMixin, TemplateView):
    template_name = 'core/test_result.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        results = self.request.session.get('test_results', {})
        if not results:
            messages.error(self.request, 'لا توجد نتائج للعرض')
            return context
        context.update(results)
        context['test_type'] = 'similar_on_pages'
        self.request.session.pop('test_results', None)
        self.request.session.pop('test_index', None)
        return context




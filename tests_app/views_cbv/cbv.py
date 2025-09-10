"""
Class-Based Views للـ Tests App
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, FormView, DetailView
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator

from core.models import Student, TestSession
from tests_app.services.test_service import TestService


class TestSelectionView(LoginRequiredMixin, TemplateView):
    """صفحة اختيار الاختبار (قالب داخل tests_app)"""
    template_name = 'core/test_selection.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # الحصول على الطالب
        from core.services.user_service import UserService
        user_service = UserService()
        student = user_service.get_or_create_student(self.request.user)
        
        # إضافة بيانات الاختبار
        context['student'] = student
        context['selected_test_type'] = self.request.session.get('selected_test_type', 'similar_count')
        
        # إضافة خيارات عدد الأسئلة
        context['num_questions_options'] = [5, 10, 15, 20, 25, 30]
        
        # إضافة بيانات الأجزاء والأرباع
        from core.models import Juz, Quarter
        juz_quarters_map = {}
        
        for juz in Juz.objects.all():
            quarters = Quarter.objects.filter(juz=juz).order_by('index_in_juz')
            juz_quarters_map[juz] = {
                'quarters': quarters,
                'first_label': quarters.first().label if quarters.exists() else ''
            }
        
        context['juz_quarters_map'] = juz_quarters_map
        
        return context


class TestQuestionView(LoginRequiredMixin, DetailView):
    """صفحة سؤال الاختبار"""
    
    model = TestSession
    template_name = 'core/test_question.html'
    context_object_name = 'session'
    pk_url_kwarg = 'session_id'
    
    def get_queryset(self):
        """فلترة الجلسات حسب الطالب"""
        from core.services.user_service import UserService
        user_service = UserService()
        student = user_service.get_or_create_student(self.request.user)
        return TestSession.objects.filter(student=student)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        session = self.get_object()
        
        # الحصول على السؤال الحالي
        current_index = self.request.session.get('test_index', 0)
        questions = list(session.questions.all())
        
        if current_index < len(questions):
            context['question'] = questions[current_index]
            context['current_index'] = current_index
            context['total_questions'] = len(questions)
            context['progress'] = (current_index / len(questions)) * 100
        
        return context
    
    def post(self, request, *args, **kwargs):
        """معالجة إجابة السؤال"""
        
        session = self.get_object()
        test_service = TestService(session.student)
        
        # الحصول على السؤال الحالي
        current_index = request.session.get('test_index', 0)
        questions = list(session.questions.all())
        
        if current_index < len(questions):
            question = questions[current_index]
            answer = request.POST.get('answer', '')
            
            # حفظ الإجابة
            is_correct, message = test_service.submit_answer(question.id, answer)
            
            # الانتقال للسؤال التالي
            request.session['test_index'] = current_index + 1
            
            if current_index + 1 >= len(questions):
                # انتهاء الاختبار
                results = test_service.complete_test_session(session.id)
                request.session['test_results'] = results
                return redirect('tests:similar_count:result')
            else:
                # الانتقال للسؤال التالي
                return redirect('tests:similar_count:question', session_id=session.id)
        
        return redirect('core:main_menu')


class TestResultView(LoginRequiredMixin, TemplateView):
    """صفحة نتائج الاختبار (قالب داخل tests_app)"""
    template_name = 'core/test_result.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # الحصول على النتائج من الجلسة
        results = self.request.session.get('test_results', {})
        
        if not results:
            messages.error(self.request, 'لا توجد نتائج للعرض')
            return redirect('core:main_menu')
        
        # إضافة النتائج للسياق
        context.update(results)
        context['test_type'] = self.request.session.get('selected_test_type', 'similar_count')
        
        # تنظيف الجلسة
        self.request.session.pop('test_results', None)
        self.request.session.pop('test_index', None)
        
        return context


class TestCatalogView(TemplateView):
    """كتالوج الاختبارات"""
    
    template_name = 'core/test_catalog.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # تعريف أنواع الاختبارات
        tests = [
            {
                'key': 'similar_count',
                'title': 'عدد مواضع المتشابهات',
                'desc': 'اختبار لمعرفة عدد المواضع التي تظهر فيها عبارة معينة في القرآن الكريم',
                'available': True,
                'url': reverse('tests:similar_count:selection')
            },
            {
                'key': 'similar_positions_on_pages',
                'title': 'مواضع المتشابهات على الصفحات',
                'desc': 'اختبار لتحديد موقع كل موضع للعبارة المتشابهة (الجزء → الربع → الصفحة)',
                'available': False,
                'url': reverse('tests:similar_positions_on_pages:selection')
            },
            {
                'key': 'verse_location_quarters',
                'title': 'موقع الآيات في الأرباع',
                'desc': 'اختبار لمعرفة الربع الذي توجد فيه آية معينة',
                'available': False,
                'url': reverse('tests:verse_location_quarters:selection')
            },
            {
                'key': 'page_edges_quarters',
                'title': 'بداية ونهاية الصفحات مع الأرباع',
                'desc': 'استنتاج بدايات/نهايات الآيات بين الصفحات داخل نطاقك',
                'available': False,
                'url': None
            },
            {
                'key': 'order_juz_quarters',
                'title': 'اختبار ترتيب الأجزاء والأرباع',
                'desc': 'أسئلة لقياس ترتيب الأجزاء والأرباع وتسلسلها',
                'available': False,
                'url': None
            },
            {
                'key': 'semantic_similarities',
                'title': 'متشابهات معاني الآيات',
                'desc': 'أسئلة على التشابه الدلالي للمعاني',
                'available': False,
                'url': None
            }
        ]
        
        context['tests'] = tests
        return context


@method_decorator(require_POST, name='dispatch')
class StartTestView(LoginRequiredMixin, FormView):
    """بدء اختبار جديد"""
    
    def post(self, request, *args, **kwargs):
        """معالجة بدء الاختبار"""
        
        # الحصول على الطالب
        from core.services.user_service import UserService
        user_service = UserService()
        student = user_service.get_or_create_student(request.user)
        
        # الحصول على بيانات الاختبار
        test_type = request.session.get('selected_test_type', 'similar_count')
        selected_juz = request.POST.getlist('selected_juz', [])
        selected_quarters = request.POST.getlist('selected_quarters', [])
        num_questions = int(request.POST.get('num_questions', 10))
        difficulty = request.POST.get('difficulty', 'mixed')
        position_order = request.POST.get('position_order', 'normal')
        
        # إنشاء جلسة الاختبار
        test_service = TestService(student)
        session = test_service.create_test_session(
            test_type=test_type,
            selected_juz=[int(j) for j in selected_juz],
            selected_quarters=[int(q) for q in selected_quarters],
            num_questions=num_questions,
            difficulty=difficulty,
            position_order=position_order
        )
        
        # إعادة تعيين الفهرس
        request.session['test_index'] = 0
        
        # توجيه لسؤال الاختبار
        return redirect('tests:similar_count:question', session_id=session.id)

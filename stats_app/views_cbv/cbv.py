"""
Class-Based Views للـ Stats App
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, DetailView
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import JsonResponse

from core.models import Student
from stats_app.services.stats_service import StatsService


class StatsView(LoginRequiredMixin, TemplateView):
    """صفحة الإحصائيات الشخصية"""
    
    template_name = 'stats/stats.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # الحصول على الطالب
        from core.services.user_service import UserService
        user_service = UserService()
        student = user_service.get_or_create_student(self.request.user)
        
        # الحصول على الإحصائيات
        stats_service = StatsService()
        context['stats'] = stats_service.get_student_stats(student)
        context['recent_activity'] = stats_service.get_recent_activity(student)
        context['student'] = student
        
        return context


class LeaderboardView(TemplateView):
    """لوحة المنافسة"""
    
    template_name = 'stats/leaderboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # الحصول على اللوحة
        stats_service = StatsService()
        context['rows'] = stats_service.get_leaderboard()
        
        # إضافة الطالب الحالي إذا كان مسجل دخول
        if self.request.user.is_authenticated:
            from core.services.user_service import UserService
            user_service = UserService()
            student = user_service.get_or_create_student(self.request.user)
            context['student'] = student
            context['my_rank'] = stats_service.get_student_rank(student)
        
        return context


class StudentProfileView(DetailView):
    """صفحة ملف الطالب"""
    
    model = Student
    template_name = 'stats/student_profile.html'
    context_object_name = 'profile_student'
    pk_url_kwarg = 'student_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # الحصول على إحصائيات الطالب
        stats_service = StatsService()
        student = self.get_object()
        stats = stats_service.get_student_stats(student)
        context['stats'] = stats
        context['recent_activity'] = stats_service.get_recent_activity(student)

        # قيم إضافية تستخدمها القوالب الأخرى
        total_questions = stats.get('total_questions', 0)
        correct = stats.get('correct_answers', 0)
        wrong = stats.get('wrong_answers', 0)
        unanswered = stats.get('unanswered', 0)
        answered = correct + wrong
        accuracy_pct = (correct / answered * 100) if answered > 0 else None
        # صيغة نقاط تقريبية
        score = round((stats.get('accuracy', 0) * 0.8) + correct + stats.get('total_sessions', 0))

        context.update({
            'total_questions': total_questions,
            'answered_questions': answered,
            'correct_questions': correct,
            'wrong_questions': wrong,
            'unanswered_questions': unanswered,
            'accuracy_pct': accuracy_pct,
            'score': score,
            'completed_sessions': stats.get('total_sessions', 0),
        })
        
        # إضافة الطالب الحالي إذا كان مسجل دخول
        if self.request.user.is_authenticated:
            from core.services.user_service import UserService
            user_service = UserService()
            current_student = user_service.get_or_create_student(self.request.user)
            context['student'] = current_student
        
        return context


class ResetStatsView(LoginRequiredMixin, TemplateView):
    """صفحة إعادة تعيين الإحصائيات"""
    
    template_name = 'stats/reset_stats.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # الحصول على الطالب
        from core.services.user_service import UserService
        user_service = UserService()
        student = user_service.get_or_create_student(self.request.user)
        
        context['student'] = student
        return context
    
    def post(self, request, *args, **kwargs):
        """معالجة طلب إعادة التعيين"""
        
        # الحصول على الطالب
        from core.services.user_service import UserService
        user_service = UserService()
        student = user_service.get_or_create_student(request.user)
        
        # إعادة تعيين الإحصائيات
        stats_service = StatsService()
        success = stats_service.reset_student_stats(student)
        
        if success:
            messages.success(
                request,
                'تم إعادة تعيين إحصائياتك بنجاح! يمكنك الآن البدء من جديد.'
            )
        else:
            messages.error(
                request,
                'حدث خطأ أثناء إعادة تعيين الإحصائيات. حاول مرة أخرى.'
            )
        
        return redirect('stats_app:stats')

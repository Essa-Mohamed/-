"""
Class-Based Views للـ Core App
"""
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import TemplateView, FormView
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import Http404

from core.services.user_service import UserService
from core.forms import LoginForm, SignupForm
from core.models import Complaint
from core.views import COMPLAINT_TYPES


def check_test_permissions(user):
    """التحقق من صلاحيات المستخدم للوصول لامتحانات المتشابهات"""
    # الإيميل المسموح له بالوصول
    ALLOWED_EMAIL = "essagamer91@gmail.com"
    
    if user.email != ALLOWED_EMAIL:
        raise Http404("هذه الميزة غير متاحة حالياً. ستكون متاحة قريباً!")


class MainMenuView(LoginRequiredMixin, TemplateView):
    """الصفحة الرئيسية للمستخدمين المسجلين"""
    
    template_name = 'core/main_menu.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # الحصول على الطالب
        user_service = UserService()
        student = user_service.get_or_create_student(self.request.user)
        
        # إضافة بيانات الطالب للسياق
        context['student'] = student
        
        # إضافة الإحصائيات والترتيب
        from stats_app.services.stats_service import StatsService
        stats_service = StatsService()
        stats_data = stats_service.get_student_stats(student)
        
        # تحويل البيانات لتتوافق مع template الصفحة الرئيسية
        context['stats'] = {
            'exams': stats_data['total_sessions'],
            'correct': stats_data['correct_answers'],
            'wrong': stats_data['wrong_answers'],
            'unanswered': stats_data['unanswered']
        }
        context['my_rank'] = stats_service.get_student_rank(student)
        
        return context


class AccountSettingsView(LoginRequiredMixin, FormView):
    """صفحة إعدادات الحساب"""
    
    template_name = 'core/account_settings.html'
    form_class = None  # سيتم تحديده في get_form_class
    success_url = reverse_lazy('core:account_settings')
    
    def get_form_class(self):
        """تحديد نوع النموذج حسب الطلب"""
        if self.request.method == 'POST':
            action = self.request.POST.get('action')
            if action == 'update_profile':
                from core.forms import ProfileUpdateForm
                return ProfileUpdateForm
            elif action == 'change_password':
                from core.forms import PasswordChangeForm
                return PasswordChangeForm
        
        # افتراضياً، نموذج تحديث الملف الشخصي
        from core.forms import ProfileUpdateForm
        return ProfileUpdateForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # الحصول على الطالب
        user_service = UserService()
        student = user_service.get_or_create_student(self.request.user)
        context['student'] = student
        
        # تمرير نماذج متوافقة مع القالب
        from core.forms import ProfileUpdateForm, PasswordChangeForm
        
        # إنشاء النماذج مع البيانات الأولية
        if self.request.method == 'POST':
            action = self.request.POST.get('action')
            if action == 'update_profile':
                context['profile_form'] = ProfileUpdateForm(self.request.POST, self.request.FILES)
            else:
                context['profile_form'] = ProfileUpdateForm(initial={
                    'display_name': student.display_name,
                    'email': student.user.email,
                    'skin': student.skin or 'default',
                })
            
            if action == 'change_password':
                context['password_form'] = PasswordChangeForm(self.request.POST)
            else:
                context['password_form'] = PasswordChangeForm()
        else:
            context['profile_form'] = ProfileUpdateForm(initial={
                'display_name': student.display_name,
                'email': student.user.email,
                'skin': student.skin or 'default',
            })
            context['password_form'] = PasswordChangeForm()
        
        return context
    
    def form_valid(self, form):
        """معالجة النموذج الصحيح"""
        
        user_service = UserService()
        student = user_service.get_or_create_student(self.request.user)
        
        action = self.request.POST.get('action')
        if action == 'update_profile':
            # تحديث الملف الشخصي
            form_data = form.cleaned_data.copy()

            # لا ترسل avatar=None حتى لا يتم مسحه
            avatar_file = self.request.FILES.get('avatar')
            if avatar_file:
                form_data['avatar'] = avatar_file
            else:
                form_data.pop('avatar', None)

            # حذف الصورة فقط إذا طُلب صراحة
            if self.request.POST.get('remove_avatar') == '1':
                form_data['remove_avatar'] = True

            # تأكيد قيمة skin الافتراضية
            if not form_data.get('skin'):
                form_data['skin'] = 'default'
            
            # التحقق من صحة البيانات
            errors = user_service.validate_student_data(form_data)
            if errors:
                for field, error in errors.items():
                    form.add_error(field, error)
                return self.form_invalid(form)
            
            # تحديث الطالب
            try:
                user_service.update_student_profile(student, **form_data)
                messages.success(self.request, 'تم تحديث الملف الشخصي بنجاح!')
            except Exception as e:
                messages.error(self.request, f'حدث خطأ أثناء تحديث الملف الشخصي: {str(e)}')
                return self.form_invalid(form)
            
        elif action == 'change_password':
            # تغيير كلمة المرور
            current_password = form.cleaned_data.get('current_password')
            new_password = form.cleaned_data.get('new_password')
            
            if not current_password or not new_password:
                messages.error(self.request, 'يجب إدخال كلمة المرور الحالية والجديدة')
                return self.form_invalid(form)
            
            # التحقق من كلمة المرور الحالية
            if not self.request.user.check_password(current_password):
                form.add_error('current_password', 'كلمة المرور الحالية غير صحيحة')
                return self.form_invalid(form)
            
            # تغيير كلمة المرور
            try:
                self.request.user.set_password(new_password)
                self.request.user.save()
                # تحديث جلسة المستخدم لتجنب تسجيل الخروج
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(self.request, self.request.user)
                messages.success(self.request, 'تم تغيير كلمة المرور بنجاح!')
            except Exception as e:
                messages.error(self.request, f'حدث خطأ أثناء تغيير كلمة المرور: {str(e)}')
                return self.form_invalid(form)
        
        return super().form_valid(form)


class CustomLoginView(LoginView):
    """تسجيل الدخول المخصص"""
    
    template_name = 'core/login.html'
    form_class = LoginForm
    redirect_authenticated_user = True
    
    def get_success_url(self):
        """تحديد الصفحة بعد تسجيل الدخول"""
        return reverse_lazy('core:main_menu')
    
    def get_context_data(self, **kwargs):
        """إضافة النموذج إلى السياق"""
        context = super().get_context_data(**kwargs)
        if 'form' not in context:
            context['form'] = self.get_form()
        return context
    
    def form_valid(self, form):
        """معالجة النموذج الصحيح"""
        remember_me = form.cleaned_data.get('remember_me')
        
        # تسجيل الدخول
        from django.contrib.auth import login
        login(self.request, form.get_user())
        
        # إعداد session للـ remember me
        if not remember_me:
            self.request.session.set_expiry(0)  # انتهاء الجلسة عند إغلاق المتصفح
        else:
            self.request.session.set_expiry(60 * 60 * 24 * 30)  # 30 يوم
        
        return super().form_valid(form)


class CustomLogoutView(LogoutView):
    """تسجيل الخروج المخصص"""
    
    next_page = reverse_lazy('core:landing')


class LandingView(TemplateView):
    """الصفحة الرئيسية - تتحقق من حالة تسجيل الدخول"""
    
    template_name = 'core/landing.html'
    
    def get(self, request, *args, **kwargs):
        # إذا كان المستخدم مسجل دخول، وجهه للصفحة الرئيسية
        if request.user.is_authenticated:
            return redirect('core:main_menu')
        
        # إذا لم يكن مسجل دخول، اعرض صفحة الهبوط
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # إضافة إحصائيات عامة
        from stats_app.services.stats_service import StatsService
        stats_service = StatsService()
        context['global_stats'] = stats_service.get_global_stats()
        
        return context


class SignupView(FormView):
    """إنشاء حساب جديد"""
    
    template_name = 'core/signup.html'
    form_class = SignupForm
    success_url = reverse_lazy('core:login')
    
    def get_context_data(self, **kwargs):
        """إضافة النموذج إلى السياق"""
        context = super().get_context_data(**kwargs)
        if 'form' not in context:
            context['form'] = self.get_form()
        return context
    
    def form_valid(self, form):
        """معالجة النموذج الصحيح"""
        
        # إنشاء المستخدم
        user = form.save()
        
        # الطالب سيتم إنشاؤه تلقائياً بواسطة الإشارة (signal)
        # في core/signals.py
        
        messages.success(
            self.request,
            'تم إنشاء الحساب بنجاح! يمكنك الآن تسجيل الدخول.'
        )

        return super().form_valid(form)


class ComplaintView(LoginRequiredMixin, TemplateView):
    """إرسال شكوى أو اقتراح"""

    template_name = 'core/complaint.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_service = UserService()
        student = user_service.get_or_create_student(self.request.user)
        context.update({'student': student, 'types': COMPLAINT_TYPES, 'hide_footer': False})
        return context

    def post(self, request, *args, **kwargs):
        user_service = UserService()
        student = user_service.get_or_create_student(request.user)
        cats = request.POST.getlist('category')
        txt = request.POST.get('text', '').strip()
        if not txt and not cats:
            messages.error(request, 'لا يمكن إرسال شكوى فارغة.')
            return self.get(request, *args, **kwargs)
        prefix = f"[{', '.join(cats)}] " if cats else ''
        Complaint.objects.create(student=student, text=prefix + txt if txt else prefix)
        messages.success(request, '📝 تم إرسال الشكوى/الاقتراح بنجاح. شكراً لك على مساعدتنا في تحسين المنصة!')
        return redirect('core:main_menu')


class AdminComplaintsView(UserPassesTestMixin, LoginRequiredMixin, TemplateView):
    """عرض وإدارة الشكاوى للمشرفين"""

    template_name = 'core/complaint_admin.html'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        comps = Complaint.objects.select_related('student__user').order_by('-created_at')
        context.update({'complaints': comps, 'hide_footer': False})
        return context

    def post(self, request, *args, **kwargs):
        cid = request.POST.get('complaint_id')
        action = request.POST.get('action')
        if cid and action:
            try:
                c = Complaint.objects.get(id=cid)
                if action == 'toggle':
                    c.resolved = not c.resolved
                    c.save()
                    status = 'تم حلها' if c.resolved else 'غير محلولة'
                    messages.success(request, f"✅ تم تحديث حالة الشكوى #{cid} إلى: {status}")
            except Complaint.DoesNotExist:
                messages.error(request, 'الشكوى غير موجودة.')
        return self.get(request, *args, **kwargs)

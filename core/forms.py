"""
Forms للـ Core App
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class LoginForm(forms.Form):
    """نموذج تسجيل الدخول"""
    
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'اسم المستخدم أو البريد الإلكتروني (مثال: mohamed139 أو example@gmail.com)',
            'dir': 'ltr'
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'كلمة المرور',
            'dir': 'ltr'
        })
    )
    
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def __init__(self, *args, **kwargs):
        # إزالة request من kwargs إذا كان موجوداً
        kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.user_cache = None
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        
        if username and password:
            from django.contrib.auth import authenticate
            from django.contrib.auth.models import User
            
            # محاولة تسجيل الدخول باسم المستخدم أولاً
            self.user_cache = authenticate(username=username, password=password)
            
            # إذا فشل، جرب البحث بالإيميل
            if self.user_cache is None:
                try:
                    user = User.objects.get(email=username)
                    self.user_cache = authenticate(username=user.username, password=password)
                except User.DoesNotExist:
                    pass
            
            if self.user_cache is None:
                raise forms.ValidationError('اسم المستخدم أو البريد الإلكتروني أو كلمة المرور غير صحيحة')
            elif not self.user_cache.is_active:
                raise forms.ValidationError('هذا الحساب غير نشط')
        
        return cleaned_data
    
    def get_user(self):
        return self.user_cache


class SignupForm(UserCreationForm):
    """نموذج إنشاء حساب جديد"""
    
    # إضافة حقل اسم العرض
    display_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'اسم العرض (مثال: خالد محمد)',
            'dir': 'rtl'
        })
    )
    
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'مثال: example@gmail.com',
            'dir': 'ltr'
        })
    )
    
    class Meta:
        model = User
        fields = ('username', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        # إزالة request من kwargs إذا كان موجوداً
        kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # تخصيص حقول كلمة المرور
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'كلمة المرور',
            'dir': 'ltr'
        })
        
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'تأكيد كلمة المرور',
            'dir': 'ltr'
        })
        
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'اسم المستخدم (بدون مسافات، مثال: mohamed139)',
            'dir': 'ltr'
        })
    
    def clean_username(self):
        """تنظيف اسم المستخدم - يجب أن يكون بدون مسافات"""
        username = self.cleaned_data.get('username')
        if username:
            username = username.strip()
            
            # التحقق من وجود مسافات
            if ' ' in username:
                raise forms.ValidationError('اسم المستخدم لا يمكن أن يحتوي على مسافات')
            
            # التحقق من الأحرف المسموحة
            import re
            if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
                raise forms.ValidationError('اسم المستخدم يمكن أن يحتوي على أحرف إنجليزية وأرقام وشرطة سفلية ونقطة وشرطة فقط')
            
            # التحقق من أن الاسم لا يبدأ أو ينتهي بنقطة أو شرطة
            if username.startswith(('.', '-')) or username.endswith(('.', '-')):
                raise forms.ValidationError('اسم المستخدم لا يمكن أن يبدأ أو ينتهي بنقطة أو شرطة')
            
            # التحقق من عدم وجود اسم المستخدم مكرر
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError('اسم المستخدم مستخدم بالفعل')
        
        return username
    
    def clean_display_name(self):
        """تنظيف اسم العرض"""
        display_name = self.cleaned_data.get('display_name')
        if display_name:
            display_name = display_name.strip()
            if not display_name:
                raise forms.ValidationError('اسم العرض لا يمكن أن يكون فارغاً')
        return display_name
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        # حفظ الإيميل إذا كان موجوداً
        email = self.cleaned_data.get('email')
        if email:
            user.email = email
        
        if commit:
            user.save()
            # إنشاء ملف شخصي للطالب مع اسم العرض
            from students.models import Student
            Student.objects.create(
                user=user,
                display_name=self.cleaned_data['display_name']
            )
        
        return user


class ProfileUpdateForm(forms.Form):
    """نموذج تحديث الملف الشخصي"""
    
    display_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'اسم العرض'
        })
    )
    
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'البريد الإلكتروني (اختياري)'
        })
    )
    
    skin = forms.ChoiceField(
        choices=[
            ('default', 'الافتراضي'),
            ('skin1', 'الجلد الأول'),
            ('skin2', 'الجلد الثاني'),
            ('skin3', 'الجلد الثالث'),
            ('skin4', 'الجلد الرابع'),
        ],
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    avatar = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )
    
    # حقول كلمة المرور (اختيارية)
    current_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'كلمة المرور الحالية',
            'dir': 'ltr'
        })
    )
    
    new_password = forms.CharField(
        required=False,
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'كلمة المرور الجديدة',
            'dir': 'ltr'
        })
    )
    
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'تأكيد كلمة المرور الجديدة',
            'dir': 'ltr'
        })
    )
    
    def __init__(self, *args, **kwargs):
        # إزالة request من kwargs إذا كان موجوداً
        kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        current_password = cleaned_data.get('current_password')
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        # إذا تم إدخال أي من حقول كلمة المرور، يجب إدخالها جميعاً
        if any([current_password, new_password, confirm_password]):
            if not all([current_password, new_password, confirm_password]):
                raise forms.ValidationError('يجب إدخال جميع حقول كلمة المرور')
            
            if new_password != confirm_password:
                raise forms.ValidationError('كلمة المرور الجديدة وتأكيدها غير متطابقتين')
        
        return cleaned_data


class PasswordChangeForm(forms.Form):
    """نموذج تغيير كلمة المرور"""
    
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'كلمة المرور الحالية',
            'dir': 'ltr'
        })
    )
    
    new_password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'كلمة المرور الجديدة',
            'dir': 'ltr'
        })
    )
    
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'تأكيد كلمة المرور الجديدة',
            'dir': 'ltr'
        })
    )
    
    def __init__(self, *args, **kwargs):
        # إزالة request من kwargs إذا كان موجوداً
        kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if new_password and confirm_password:
            if new_password != confirm_password:
                raise forms.ValidationError('كلمات المرور غير متطابقة')
        
        return cleaned_data


class ComplaintForm(forms.Form):
    """نموذج الإبلاغ والملاحظات"""
    
    COMPLAINT_TYPES = [
        ('bug', 'مشكلة تقنية'),
        ('suggestion', 'اقتراح'),
        ('content', 'محتوى'),
        ('other', 'أخرى'),
    ]
    
    complaint_type = forms.ChoiceField(
        choices=COMPLAINT_TYPES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    subject = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'موضوع الإبلاغ'
        })
    )
    
    message = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'تفاصيل الإبلاغ أو الاقتراح',
            'rows': 5
        })
    )
    
    contact_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'البريد الإلكتروني (اختياري)',
            'dir': 'ltr'
        })
    )
"""
Forms for the Quran memorization assistant.

These forms provide simple interfaces for capturing the student’s
display name and complaints. Additional forms for selecting tests
and answering questions can be implemented similarly.
"""
from django import forms  # type: ignore
from django.contrib.auth.models import User  # type: ignore
from .models import Complaint
from django.contrib.auth.forms import PasswordChangeForm


class StudentNameForm(forms.Form):
    """Capture a student’s display name to create a user account on the fly."""

    display_name = forms.CharField(label='اسم الطالب', max_length=100)


class ComplaintForm(forms.ModelForm):
    """Form for submitting a complaint."""

    class Meta:
        model = Complaint
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 4, 'cols': 40, 'placeholder': 'اكتب شكواك هنا...'}),
        }

class AccountForm(forms.Form):
    display_name = forms.CharField(label='اسم العرض', max_length=100)
    email = forms.EmailField(label='البريد الإلكتروني (اختياري)', required=False)
    avatar = forms.ImageField(label='الصورة الشخصية (اختياري)', required=False)

class PasswordChangeTightForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'كلمة المرور الحالية'
        self.fields['new_password1'].label = 'كلمة المرور الجديدة'
        self.fields['new_password2'].label = 'تأكيد كلمة المرور الجديدة'
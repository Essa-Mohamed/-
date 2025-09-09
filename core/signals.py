from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Student
from .services.user_service import UserService

@receiver(post_save, sender=User)
def ensure_student_profile(sender, instance, created, **kwargs):
    if created:
        # إنشاء ملف شخصي للطالب إذا لم يكن موجوداً
        # سيتم إنشاؤه بواسطة SignupForm.save() مباشرة
        pass

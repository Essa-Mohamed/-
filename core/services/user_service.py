"""
خدمة إدارة المستخدمين والطلاب
"""
from typing import Dict, Optional
from django.contrib.auth.models import User
from django.db import transaction
from django.core.exceptions import ValidationError

from students.models import Student


class UserService:
    """خدمة إدارة المستخدمين والطلاب"""
    
    def create_student(self, user: User, **kwargs) -> Student:
        """إنشاء طالب جديد"""
        
        with transaction.atomic():
            # استخدام اسم المستخدم الأصلي (مع المسافات) كـ display_name
            display_name = kwargs.get('display_name')
            if not display_name:
                # إذا لم يتم تمرير display_name، استخدم username مع استبدال الشرطة السفلية بمسافات
                display_name = user.username.replace('_', ' ')
            
            student = Student.objects.create(
                user=user,
                display_name=display_name,
                skin=kwargs.get('skin', 'default')
            )
            
            return student
    
    def update_student_profile(self, student: Student, **kwargs) -> Student:
        """تحديث ملف الطالب دون مسح الصورة ما لم تُرسل صراحة.

        ملاحظة: إذا لم يتم تمرير المفتاح 'avatar' أو كانت قيمته فارغة/None،
        فلن نقوم بتغيير صورة الطالب الحالية.
        """
        with transaction.atomic():
            if 'display_name' in kwargs:
                student.display_name = kwargs['display_name']

            if 'skin' in kwargs and kwargs['skin']:
                student.skin = kwargs['skin']

            # تحديث الإيميل
            if 'email' in kwargs:
                email = kwargs['email']
                if email and email.strip():
                    student.user.email = email.strip()
                else:
                    student.user.email = ''  # حفظ كقيمة فارغة
                student.user.save()

            # حذف الصورة إذا طُلب صراحة
            if kwargs.get('remove_avatar') and student.avatar:
                student.avatar.delete(save=False)
                student.avatar = None

            # تحديث الصورة إذا وصل ملف فعلي وغير فارغ
            if 'avatar' in kwargs:
                avatar_file = kwargs.get('avatar')
                if avatar_file:
                    student.avatar = avatar_file

            student.save()
            return student
    
    def get_student_by_user(self, user: User) -> Optional[Student]:
        """الحصول على الطالب من المستخدم"""
        
        try:
            return Student.objects.get(user=user)
        except Student.DoesNotExist:
            return None
    
    def get_or_create_student(self, user: User) -> Student:
        """الحصول على الطالب أو إنشاؤه إذا لم يكن موجوداً"""
        
        student = self.get_student_by_user(user)
        
        if not student:
            student = self.create_student(user)
        
        return student
    
    def validate_student_data(self, data: Dict) -> Dict:
        """التحقق من صحة بيانات الطالب"""
        
        errors = {}
        
        if 'display_name' in data:
            display_name = data['display_name'].strip()
            if not display_name:
                errors['display_name'] = 'لا يمكن أن يكون حقل اسم العرض فارغاً'
            elif len(display_name) < 2:
                errors['display_name'] = 'اسم العرض يجب أن يكون على الأقل حرفين'
            elif len(display_name) > 100:
                errors['display_name'] = 'اسم العرض يجب أن يكون أقل من 100 حرف'
        
        if 'email' in data:
            email = data['email']
            if email and email.strip():
                # التحقق من صحة الإيميل فقط إذا كان غير فارغ
                from django.core.validators import validate_email
                from django.core.exceptions import ValidationError
                try:
                    validate_email(email.strip())
                except ValidationError:
                    errors['email'] = 'البريد الإلكتروني غير صحيح'
        
        if 'skin' in data:
            valid_skins = ['default', 'skin1', 'skin2', 'skin3', 'skin4']
            if data['skin'] not in valid_skins:
                errors['skin'] = 'الجلد المحدد غير صحيح'
        
        return errors

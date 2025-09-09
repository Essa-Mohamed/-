import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class AlphaNumericPasswordValidator:
    """
    يفرض احتواء كلمة المرور على الأقل على حرف واحد ورقم واحد
    بالإضافة إلى حد الطول (الذي يفرضه MinimumLengthValidator).
    """
    def validate(self, password, user=None):
        if not re.search(r'[A-Za-z]', password or ''):
            raise ValidationError(_("يجب أن تحتوي كلمة المرور على حرف واحد على الأقل."), code="password_no_letter")
        if not re.search(r'\d', password or ''):
            raise ValidationError(_("يجب أن تحتوي كلمة المرور على رقم واحد على الأقل."), code="password_no_digit")

    def get_help_text(self):
        return _("يجب أن تحتوي كلمة المرور على أحرف وأرقام على الأقل.")

from .models import Student
from django.conf import settings


def inject_student(request):
    if request.user.is_authenticated:
        student, _ = Student.objects.get_or_create(
            user=request.user, defaults={'display_name': request.user.username}
        )
        return {'student': student}
    return {}


def inject_version(request):
    label = getattr(settings, "VERSION_LABEL", "")
    return {
        "APP_NAME": "Mutawatir",
        "APP_VERSION": label,
        "IS_ALPHA": "alpha" in (label or "").lower(),
    }
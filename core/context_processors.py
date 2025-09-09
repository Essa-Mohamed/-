from .models import Student
from django.conf import settings


def inject_student(request):
    if request.user.is_authenticated:
        try:
            student = Student.objects.get(user=request.user)
        except Student.DoesNotExist:
            student = None
        return {"student": student}
    return {}


def inject_version(request):
    label = getattr(settings, "VERSION_LABEL", "")
    return {
        "APP_NAME": "Mutawatir",
        "APP_VERSION": label,
        "IS_ALPHA": "alpha" in (label or "").lower(),
    }
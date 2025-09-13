from django.db import models
from django.contrib.auth.models import User


class Student(models.Model):
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    def avatar_url(self):
        try:
            if self.avatar and hasattr(self.avatar, "url"):
                return self.avatar.url
        except Exception:
            pass
        return ""

    """A simple student profile linked to the built-in User model."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=100)
    skin = models.CharField(max_length=50, default='default', help_text='Skin theme for the student')

    def __str__(self) -> str:
        return self.display_name


class Complaint(models.Model):
    """A complaint or suggestion submitted by a student."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Complaint by {self.student}: {self.text[:30]}"

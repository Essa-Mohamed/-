from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db import models

class EmailOrUsernameModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if not username or not password:
            return None
        qs = UserModel.objects.filter(
            models.Q(username__iexact=username) | models.Q(email__iexact=username)
        )
        for user in qs:
            if user.check_password(password):
                return user
        return None

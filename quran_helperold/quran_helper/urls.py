from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # يضيف view باسم set_language على /i18n/setlang/
    path("i18n/", include("django.conf.urls.i18n")),

    # كل مسارات التطبيق
    path("", include(("core.urls", "core"), namespace="core")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
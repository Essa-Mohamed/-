from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),

    # يضيف view باسم set_language على /i18n/setlang/
    path("i18n/", include("django.conf.urls.i18n")),

    # كل مسارات التطبيق
    path("", include(("core.urls", "core"), namespace="core")),

    # مسارات جديدة مقسمة حسب التطبيقات
    path("tests/", include(("tests_app.urls", "tests_app"), namespace="tests")),
    path("mushaf/", include(("mushaf_app.urls", "mushaf_app"), namespace="mushaf")),
    path("complaints/", include(("complaints_app.urls", "complaints_app"), namespace="complaints")),
    path("api/v1/", include(("api_v1.urls", "api_v1"), namespace="api_v1")),
    path("stats/", include(("stats_app.urls", "stats_app"), namespace="stats")),

    # Redirects للحفاظ على التوافق
    path("stats/reset/", RedirectView.as_view(url="/stats/reset/", permanent=False)),
    path("leaderboard/", RedirectView.as_view(url="/stats/leaderboard/", permanent=False)),
    path("profile/<int:student_id>/", RedirectView.as_view(url="/stats/profile/%(student_id)s/", permanent=False)),
    # API redirects
    path("api/quarter/<int:qid>/pages/", RedirectView.as_view(url="/api/v1/quarter/%(qid)s/pages/", permanent=False)),
    path("api/page/<int:pno>/ayat/", RedirectView.as_view(url="/api/v1/page/%(pno)s/ayat/", permanent=False)),
    path("api/test/pages/select-first/", RedirectView.as_view(url="/api/v1/test/pages/select-first/", permanent=False)),
    # Test redirects
    path("test/", RedirectView.as_view(url="/tests/", permanent=False)),
    path("start/", RedirectView.as_view(url="/tests/", permanent=False)),
    path("test-question/", RedirectView.as_view(url="/tests/", permanent=False)),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# ===== FILE: core/urls.py =====
from django.urls import path
from . import views
from .views_cbv.cbv import (
    MainMenuView, AccountSettingsView, CustomLoginView, 
    CustomLogoutView, LandingView, SignupView
)

app_name = "core"

urlpatterns = [
    # Landing على /
    path("", LandingView.as_view(), name="landing"),

    # Main menu
    path("home/", MainMenuView.as_view(), name="main_menu"),

    # Auth
    path("login/", CustomLoginView.as_view(), name="login"),
    path("signup/", SignupView.as_view(), name="signup"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),

    # Test flow (انتقلت إلى tests_app). نُبقي فقط مسار الإبلاغ لأنه مرتبط بالقالب الحالي
    path("report-question/", views.report_question, name="report_question"),

    # Similar on pages test flow
    path("pages/choose-juz/", views.pages_choose_juz, name="pages_choose_juz"),
    path("pages/choose-quarter/<int:juz_no>/", views.pages_choose_quarter, name="pages_choose_quarter"),
    path("pages/quarter-pick/<int:qid>/", views.pages_quarter_pick, name="pages_quarter_pick"),

    # Complaints
    path("complaint/", views.complaint, name="complaint"),
    path("admin/complaints/", views.admin_complaints, name="admin_complaints"),

    path("account/", AccountSettingsView.as_view(), name="account_settings"),

    # Stats moved to stats_app
    # API moved to api_v1
    # Tests moved to tests_app (تمت إزالة المسارات المكررة هنا لتفادي التداخل)









]
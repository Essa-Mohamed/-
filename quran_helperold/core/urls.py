from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    # Landing على /
    path("", views.landing, name="landing"),

    # Main menu
    path("home/", views.main_menu, name="main_menu"),

    # Auth
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),

    # Test flow
    path("test/", views.test_selection, name="test_selection"),
    path("start/", views.start_test, name="start_test"),
    path("test-question/", views.test_question, name="test_question"),
    path("report-question/", views.report_question, name="report_question"),

    # Complaints
    path("complaint/", views.complaint, name="complaint"),
    path("admin/complaints/", views.admin_complaints, name="admin_complaints"),

    path("account/", views.account_settings, name="account_settings"),

    path("stats/", views.stats, name="stats"),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path("tests/", views.test_catalog, name="test_catalog"),
    path("api/quarter/<int:qid>/pages/", views.quarter_pages_api, name="quarter_pages_api"),
    path("api/page/<int:pno>/ayat/", views.page_ayat_api, name="page_ayat_api"),
    path("quarter/<int:qid>/pages/", views.quarter_pages_view, name="quarter_pages_view"),
    path("page-svg/<int:pno>.svg", views.page_svg, name="page_svg_proxy"),
    path("test/pages/choose-juz/", views.pages_choose_juz, name="pages_choose_juz"),
    path("test/pages/choose-quarter/<int:juz_no>/", views.pages_choose_quarter, name="pages_choose_quarter"),
    path("test/pages/choose-quarter/<int:juz_no>/", views.pages_choose_quarter, name="pages_choose_quarter"),
    path("test/pages/quarter/<int:qid>/", views.pages_quarter_pick, name="pages_quarter_pick"),
    path("api/test/pages/select-first/", views.api_pages_select_first, name="api_pages_select_first"),
    path("test/pages/quarter/<int:qid>/viewer/", views.pages_quarter_viewer, name="pages_quarter_viewer"),
    path("test/page-svg/<int:pno>/", views.page_svg, name="page_svg"),









]

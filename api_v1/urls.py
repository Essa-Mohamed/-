from django.urls import path
from . import views

app_name = "api_v1"

urlpatterns = [
    # API endpoints
    path("quarter/<int:qid>/pages/", views.quarter_pages_api, name="quarter_pages_api"),
    path("page/<int:pno>/ayat/", views.page_ayat_api, name="page_ayat_api"),
    path("test/pages/select-first/", views.api_pages_select_first, name="api_pages_select_first"),
    path("ping/", views.ping, name="ping"),
]



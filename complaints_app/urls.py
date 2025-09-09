from django.urls import path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="core:complaint", permanent=False), name="complaints_root"),
    path("admin/", RedirectView.as_view(pattern_name="core:admin_complaints", permanent=False), name="complaints_admin"),
]



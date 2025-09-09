from django.urls import path
from django.views.generic import RedirectView

urlpatterns = [
    # عرض أرباع وصفحات
    path("quarter/<int:qid>/pages/", RedirectView.as_view(pattern_name="core:quarter_pages_view", permanent=False), name="quarter_pages"),
    path("page-svg/<int:pno>.svg", RedirectView.as_view(pattern_name="core:page_svg_proxy", permanent=False), name="page_svg_proxy"),
    path("page/<int:pno>/", RedirectView.as_view(pattern_name="core:page_svg", permanent=False), name="page_svg"),
]



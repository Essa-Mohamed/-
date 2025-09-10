from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    # عرض أرباع وصفحات
    path("quarter/<int:qid>/pages/", RedirectView.as_view(pattern_name="core:quarter_pages_view", permanent=False), name="quarter_pages"),
    path("page-svg/<int:pno>.svg", RedirectView.as_view(pattern_name="core:page_svg_proxy", permanent=False), name="page_svg_proxy"),
    path("page/<int:pno>/", RedirectView.as_view(pattern_name="core:page_svg", permanent=False), name="page_svg"),

    # Demo using elec_mushaf data
    path("demo/", views.demo_index, name="demo_index"),
    path("demo/<int:pno>/", views.demo_page, name="demo_page"),

    # Ayat embed (KSU official interface)
    path("ayat/", views.ayat_embed, name="ayat_embed"),
    
    # المصحف التفاعلي
    path("", views.interactive_mushaf_index, name="interactive_mushaf_index"),
]



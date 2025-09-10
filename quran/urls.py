from django.urls import path
from . import views

app_name = 'quran'

urlpatterns = [
    path("mushaf/page/<int:num>/", views.mushaf_page, name="mushaf_page"),
    path("api/page/<int:num>/meta/", views.page_meta_api, name="page_meta_api"),
    path("mushaf/demo/", views.mushaf_demo, name="mushaf_demo"),
]


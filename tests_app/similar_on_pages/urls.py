from django.urls import path
from . import views

app_name = "similar_on_pages"

urlpatterns = [
    path("", views.selection, name="selection"),
    path("start/", views.start, name="start"),
    path("question/", views.question, name="question"),
    path("report/", views.report, name="report"),
]
from django.urls import path
from . import views

app_name = "similar_count"

urlpatterns = [
    path("", views.selection, name="selection"),
    path("start/", views.start, name="start"),
    path("question/", views.question, name="question"),
    path("result/", views.result, name="result"),
    path("report/", views.report, name="report"),
]
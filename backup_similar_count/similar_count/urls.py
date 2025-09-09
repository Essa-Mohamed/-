from django.urls import path
from .views_cbv import SelectionView, StartView, QuestionView, ResultView

app_name = "similar_count"

urlpatterns = [
    path("", SelectionView.as_view(), name="selection"),
    path("start/", StartView.as_view(), name="start"),
    path("question/<int:session_id>/", QuestionView.as_view(), name="question"),
    path("result/", ResultView.as_view(), name="result"),
]



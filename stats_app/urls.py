from django.urls import path
from . import views
from .views_cbv.cbv import StatsView, LeaderboardView, StudentProfileView, ResetStatsView

app_name = "stats_app"

urlpatterns = [
    path("", StatsView.as_view(), name="stats"),
    path("reset/", ResetStatsView.as_view(), name="reset_stats"),
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path("profile/<int:student_id>/", StudentProfileView.as_view(), name="student_profile"),
]


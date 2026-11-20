from django.urls import path

from .views import leaderboard


app_name = "leaderboard"
urlpatterns = [path("", leaderboard, name="index")]

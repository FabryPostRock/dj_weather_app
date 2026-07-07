from django.urls import path

from weather.views import DailyWeatherEventAPIView


app_name = "weather"

urlpatterns = [
    path(
        "events/",
        DailyWeatherEventAPIView.as_view(),
        name="weather-events",
    ),
]
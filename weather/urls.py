from django.urls import path

from weather.views import (
    DailyWeatherEventAPIView,
    OidioForecastAPIView,
)


app_name = "weather"

urlpatterns = [
    path(
        "events/",
        DailyWeatherEventAPIView.as_view(),
        name="weather-events",
    ),
    path(
        "forecast/",
        OidioForecastAPIView.as_view(),
        name="weather-forecast",
    ),
]
from django.shortcuts import render

import logging

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from weather.serializers import (
    DailyWeatherInputSerializer,
    DailyWeatherOutputSerializer,
    ForecastRequestSerializer,
    ForecastResponseSerializer,
)
from weather.services import (
    process_daily_weather,
    process_oidio_forecast_days,
)


logger = logging.getLogger(__name__)


class DailyWeatherEventAPIView(APIView):
    """
    REST API per il Problema 1.

    Riceve dati meteo giornalieri e lo stato opzionale degli eventi precedenti.
    Restituisce il nuovo stato degli eventi.

    L'API è stateless:
    - non salva events nel database;
    - non usa sessioni;
    - non mantiene memoria interna tra una chiamata e l'altra.

    Per testare :
    curl -X POST http://127.0.0.1:8000/api/weather/events/ ^
    -H "Content-Type: application/json" ^
    -d "{\"doy\":126,\"temperature\":15.94,\"bagnatura\":1,\"humidity\":97.25,\"rain\":0.0}"
    """

    # @extend_schema serve solo per la documentazione OpenAPI/Swagger generata da drf-spectacular.
    # Non cambia la logica della view.
    @extend_schema(
        request=DailyWeatherInputSerializer,
        responses={status.HTTP_200_OK: DailyWeatherOutputSerializer},
        description=(
            "Elabora i dati meteo giornalieri e restituisce lo stato aggiornato "
            "degli eventi secondo la logica del Problema 1."
        ),
    )
    def post(self, request):
        input_serializer = DailyWeatherInputSerializer(data=request.data)

        input_serializer.is_valid(raise_exception=True)

        validated_payload = input_serializer.validated_data

        logger.info(f'validated_payload : {validated_payload}')
        logger.info(
            "Processing daily weather payload for doy=%s",
            validated_payload["doy"],
        )

        output_payload = process_daily_weather(validated_payload)

        output_serializer = DailyWeatherOutputSerializer(data=output_payload)
        output_serializer.is_valid(raise_exception=True)

        return Response(
            output_serializer.validated_data,
            status=status.HTTP_200_OK,
        )



class OidioForecastAPIView(APIView):
    """
    REST API per il Problema 2.

    Riceve una sequenza multi-DOY:
    - il primo giorno contiene anche events, cioè lo stato antecedente alla sequenza;
    - i giorni successivi contengono solo dati meteo.

    Per ogni giorno, la view delega al service del Problema 2,
    che chiama il Problema 1 come black-box e salva i risultati nel DB.
    """

    @extend_schema(
        request=ForecastRequestSerializer,
        responses={status.HTTP_200_OK: ForecastResponseSerializer},
        examples=[
                OpenApiExample(
                    name="Request multi-DOY valida",
                    value={
                        "days": [
                            {
                                "doy": 284,
                                "temperature": 28.0,
                                "bagnatura": 0,
                                "humidity": 30.0,
                                "rain": 0.0,
                                "events": [
                                    {"index": 0, "X": 0.0},
                                    {"index": 1, "X": 0.0},
                                    {"index": 2, "X": 0.0},
                                    {"index": 3, "X": 0.0},
                                ],
                            },
                            {
                                "doy": 285,
                                "temperature": 30.0,
                                "bagnatura": 0,
                                "humidity": 32.0,
                                "rain": 0.0,
                            },
                            {
                                "doy": 286,
                                "temperature": 32.0,
                                "bagnatura": 0,
                                "humidity": 40.0,
                                "rain": 0.0,
                            },
                        ]
                    },
                    request_only=True,
                ),
                OpenApiExample(
                    name="Response multi-DOY valida",
                    value={
                        "days": [
                            {
                                "doy": 284,
                                "events": [
                                    {"index": 0, "X": 0.2},
                                    {"index": 1, "X": 0.1},
                                    {"index": 2, "X": 0.3},
                                    {"index": 3, "X": 0.1},
                                ],
                            },
                            {
                                "doy": 285,
                                "events": [
                                    {"index": 0, "X": 0.4},
                                    {"index": 1, "X": 0.2},
                                    {"index": 2, "X": 0.5},
                                    {"index": 3, "X": 0.4},
                                ],
                            },
                        ]
                    },
                    response_only=True,
                    status_codes=["200"],
                ),
            ],
        description=(
            "Elabora una sequenza multi-DOY per il modello Oidio. "
            "Il primo giorno deve contenere lo stato events antecedente "
            "alla sequenza. La risposta contiene, per ogni DOY, gli events "
            "risultanti."
        ),
    )
    def post(self, request):
        input_serializer = ForecastRequestSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        output_payload = process_oidio_forecast_days(
            weather_days=input_serializer.validated_data["days"],
        )

        output_serializer = ForecastResponseSerializer(data=output_payload)
        output_serializer.is_valid(raise_exception=True)

        return Response(
            output_serializer.validated_data,
            status=status.HTTP_200_OK,
        )
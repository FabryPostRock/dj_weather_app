from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ForecastDay(models.Model):
    """
    Rappresenta lo stato calcolato del modello Oidio per un singolo DOY.

    Ogni record contiene:
    - i dati meteo giornalieri;
    - lo stato finale degli eventi alla fine di quel giorno;
    - un flag processed per evitare ricalcoli dello stesso giorno.

    Il campo events è salvato come JSON perché il Problema 1 riceve e restituisce
    già gli eventi nel formato:
    [
        {"index": 0, "X": 0.2},
        {"index": 1, "X": 0.4},
    ]
    """

    doy = models.PositiveSmallIntegerField(
        unique=True,
        # Costraint a livello di api
        validators=[
            MinValueValidator(1),
            MaxValueValidator(366),
        ],
        help_text="Day Of Year, valore compreso tra 1 e 366.",
    )

    temperature = models.FloatField(
        help_text="Temperatura media giornaliera in gradi Celsius.",
    )

    bagnatura = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(1),
        ],
        help_text="Bagnatura fogliare media giornaliera: 0=asciutta, 1=bagnata.",
    )

    humidity = models.FloatField(
        validators=[
            MinValueValidator(0.0),
            MaxValueValidator(100.0),
        ],
        help_text="Umidità media giornaliera percentuale, valore compreso tra 0 e 100.",
    )

    rain = models.FloatField(
        validators=[
            MinValueValidator(0.0),
        ],
        help_text="Pioggia cumulata giornaliera in millimetri.",
    )

    events = models.JSONField(
        default=list,
        blank=True,
        help_text="Stato finale degli eventi alla fine del giorno.",
    )

    processed = models.BooleanField(
        default=False,
        help_text="Indica se il giorno è già stato processato dal modello.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["doy"]
        verbose_name = "forecast day"
        verbose_name_plural = "forecast days"
        # Costraint a livello db
        constraints = [
            models.CheckConstraint(
                condition=models.Q(doy__gte=1) & models.Q(doy__lte=366),
                name="forecastday_doy_between_1_and_366",
            ),
            models.CheckConstraint(
                condition=models.Q(bagnatura__gte=0) & models.Q(bagnatura__lte=1),
                name="forecastday_bagnatura_between_0_and_1",
            ),
            models.CheckConstraint(
                condition=models.Q(humidity__gte=0.0) & models.Q(humidity__lte=100.0),
                name="forecastday_humidity_between_0_and_100",
            ),
            models.CheckConstraint(
                condition=models.Q(rain__gte=0.0),
                name="forecastday_rain_gte_0",
            ),
        ]

    def __str__(self):
        return f"ForecastDay doy={self.doy} processed={self.processed}"

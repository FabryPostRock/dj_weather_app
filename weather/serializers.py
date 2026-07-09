from rest_framework import serializers
import logging
logger = logging.getLogger(__name__)

class EventSerializer(serializers.Serializer):
    """
    Serializer per un singolo evento.

    Ogni evento ha:
    - index: identificativo numerico dell'evento
    - X: valore di evoluzione dell'evento, compreso tra 0 e 1

    Controlla solo che, quando un evento arriva o viene restituito, abbia una struttura valida.
    """

    index = serializers.IntegerField(min_value=0)
    X = serializers.FloatField(min_value=0.0, max_value=1.0)


class DailyWeatherInputSerializer(serializers.Serializer):
    """
    Serializer per il payload di input del Problema 1.

    Prima chiamata:
    {
        "doy": 126,
        "temperature": 15.94,
        "bagnatura": 1,
        "humidity": 97.25,
        "rain": 0.0
    }

    Chiamate successive:
    {
        "doy": 127,
        "temperature": 17.15,
        "bagnatura": 1,
        "humidity": 42.35,
        "rain": 0.0,
        "events": [
            {"index": 0, "X": 0.0}
        ]
    }
    """

    doy = serializers.IntegerField(min_value=1, max_value=366)
    temperature = serializers.FloatField()
    bagnatura = serializers.IntegerField(min_value=0, max_value=1)
    humidity = serializers.FloatField(min_value=0.0, max_value=100.0)
    rain = serializers.FloatField(min_value=0.0)

    events = EventSerializer(
        many=True,
        required=False,
        default=list
    )

    def validate_events(self, events):
        """
        Verifica che non ci siano index duplicati.

        Ogni evento deve essere identificato da un index univoco.
        """

        indexes = [event["index"] for event in events]
        logger.info(f'indexes : {indexes}')
        logger.info(f'events : {events}')
        if len(indexes) != len(set(indexes)):
            raise serializers.ValidationError(
                "Gli eventi non possono avere index duplicati."
            )

        return events


class DailyWeatherOutputSerializer(serializers.Serializer):
    """
    Serializer per il payload di output del Problema 1.

    Output:
    {
        "doy": 126,
        "events": [
            {"index": 0, "X": 0.0}
        ]
    }
    """

    doy = serializers.IntegerField(min_value=1, max_value=366)
    events = EventSerializer(many=True)


class ForecastWeatherDayInputSerializer(serializers.Serializer):
    """
    Serializer per un singolo giorno meteo del Problema 2.

    Questo serializer valida solo i dati meteo.
    Non contiene events, perché gli events sono ammessi solo sul primo giorno
    della richiesta multi-DOY e vengono gestiti dal ForecastRequestSerializer.

    
    Input:

        {
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
                        {"index": 3, "X": 0.0}
                    ]
                },
                {
                    "doy": 285,
                    "temperature": 30.0,
                    "bagnatura": 0,
                    "humidity": 32.0,
                    "rain": 0.0
                },
                {
                    "doy": 286,
                    "temperature": 32.0,
                    "bagnatura": 0,
                    "humidity": 40.0,
                    "rain": 0.0
                },
                {
                    "doy": 287,
                    "temperature": 34.0,
                    "bagnatura": 0,
                    "humidity": 45.0,
                    "rain": 0.0
                }
            ]
        }
    """

    doy = serializers.IntegerField(
        min_value=1,
        max_value=366,
        help_text="Day Of Year, valore compreso tra 1 e 366.",
    )
    temperature = serializers.FloatField(
        help_text="Temperatura media giornaliera in gradi Celsius.",
    )
    bagnatura = serializers.IntegerField(
        min_value=0,
        max_value=1,
        help_text="Bagnatura fogliare: 0=foglia asciutta, 1=foglia bagnata.",
    )
    humidity = serializers.FloatField(
        min_value=0.0,
        max_value=100.0,
        help_text="Umidità media giornaliera percentuale, valore tra 0 e 100.",
    )
    rain = serializers.FloatField(
        min_value=0.0,
        help_text="Pioggia cumulata giornaliera in millimetri.",
    )
    events = EventSerializer(
        many=True,
        required=False,
        allow_empty=True,
        help_text=(
            "Stato events antecedente alla sequenza. "
            "Deve essere presente solo nel primo giorno."
        ),
    )
    
    def validate_events(self, events):
        """
        Verifica che non ci siano index duplicati.
        """

        indexes = [event["index"] for event in events]

        if len(indexes) != len(set(indexes)):
            raise serializers.ValidationError(
                "Gli eventi iniziali non possono avere index duplicati."
            )

        return events


class ForecastRequestSerializer(serializers.Serializer):
    """
    Serializer per la request multi-giornaliera del Problema 2.
    Regole:
        - la lista days deve contenere almeno 1 giorno;
        - il numero massimo di giorni è 8:
        1 giorno storico + massimo 7 giorni previsionali;
        - il primo giorno deve contenere events;
        - eventuali events presenti nei giorni successivi vengono ignorati;
        - i DOY devono essere univoci, ordinati e consecutivi.

    Formato atteso:

    {
        "days": [
            {
                "doy": 275,
                "temperature": 30.0,
                "bagnatura": 0,
                "humidity": 32.0,
                "rain": 0.0,
                "events": [
                    {"index": 0, "X": 0.7},
                    {"index": 1, "X": 0.0}
                ]
            },
            {
                "doy": 276,
                "temperature": 28.0,
                "bagnatura": 0,
                "humidity": 30.0,
                "rain": 0.0
            }
        ]
    }

    """

    MAX_TOTAL_DAYS = 8

    days = ForecastWeatherDayInputSerializer(
        many=True,
        allow_empty=False,
        help_text=(
            "Lista di giorni meteo da elaborare. "
            "Il primo giorno deve contenere anche events."
        ),
    )

    def validate_days(self, days):
        if len(days) > self.MAX_TOTAL_DAYS:
            raise serializers.ValidationError(
                "La richiesta può contenere al massimo 8 giorni: "
                "1 giorno storico + massimo 7 giorni previsionali."
            )

        first_raw_day = days[0]

        if "events" not in first_raw_day:
            raise serializers.ValidationError(
                {
                    0: {
                        "events": [
                            "Il primo giorno deve contenere il campo events "
                            "con lo stato antecedente alla sequenza."
                        ]
                    }
                }
            )

        doys = [day["doy"] for day in days]

        if len(doys) != len(set(doys)):
            raise serializers.ValidationError(
                "La richiesta non può contenere DOY duplicati."
            )

        if doys != sorted(doys):
            raise serializers.ValidationError(
                "I giorni devono essere ordinati per DOY crescente."
            )

        expected_doys = list(range(doys[0], doys[0] + len(doys)))

        if doys != expected_doys:
            raise serializers.ValidationError(
                "I DOY devono essere consecutivi."
            )

        return days



class ForecastResponseSerializer(serializers.Serializer):
    """
    Serializer per la response multi-DOY del Problema 2.

    Ogni elemento della response ha la stessa forma dell'output
    della black-box del Problema 1:

    {
        "doy": 275,
        "events": [
            {"index": 0, "X": 0.7},
            {"index": 1, "X": 0.0}
        ]
    }
    """

    days = DailyWeatherOutputSerializer(many=True)
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
    """

    doy = serializers.IntegerField(min_value=1, max_value=366)
    temperature = serializers.FloatField()
    bagnatura = serializers.IntegerField(min_value=0, max_value=1)
    humidity = serializers.FloatField(min_value=0.0, max_value=100.0)
    rain = serializers.FloatField(min_value=0.0)


class ForecastFirstWeatherDayInputSerializer(ForecastWeatherDayInputSerializer):
    """
    Serializer per il primo giorno della richiesta multi-DOY del Problema 2.

    Il primo giorno deve contenere anche events, cioè lo stato del modello
    antecedente al primo DOY della sequenza.

    Esempio:
    se la sequenza parte da doy=170, events rappresenta lo stato del doy=169.
    """

    events = EventSerializer(
        many=True,
        required=True,
        allow_empty=True,
    )

    def validate_events(self, events):
        """
        Verifica che non ci siano index duplicati nello stato iniziale.
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

    Regole:
    - la lista days deve contenere almeno 1 giorno;
    - il numero massimo di giorni è 8:
      1 giorno storico + massimo 7 giorni previsionali;
    - il primo giorno deve contenere events;
    - eventuali events presenti nei giorni successivi vengono ignorati;
    - i DOY devono essere univoci, ordinati e consecutivi.
    """

    MAX_TOTAL_DAYS = 8

    days = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False,
    )

    def validate_days(self, raw_days):
        if len(raw_days) > self.MAX_TOTAL_DAYS:
            raise serializers.ValidationError(
                "La richiesta può contenere al massimo 8 giorni: "
                "1 giorno storico + massimo 7 giorni previsionali."
            )

        first_raw_day = raw_days[0]

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

        validated_days = []
        errors = {}

        first_day_serializer = ForecastFirstWeatherDayInputSerializer(
            data=first_raw_day
        )

        if first_day_serializer.is_valid():
            validated_days.append(first_day_serializer.validated_data)
        else:
            errors[0] = first_day_serializer.errors

        for index, raw_day in enumerate(raw_days[1:], start=1):
            # Gli events eventualmente presenti nei giorni successivi
            # vengono ignorati per rispettare la semantica del Problema 2.
            raw_day_without_events = {
                key: value
                for key, value in raw_day.items()
                if key != "events"
            }

            day_serializer = ForecastWeatherDayInputSerializer(
                data=raw_day_without_events
            )

            if day_serializer.is_valid():
                validated_days.append(day_serializer.validated_data)
            else:
                errors[index] = day_serializer.errors

        if errors:
            raise serializers.ValidationError(errors)

        doys = [day["doy"] for day in validated_days]

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

        return validated_days



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
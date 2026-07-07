from rest_framework import serializers


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
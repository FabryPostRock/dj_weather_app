from django.test import SimpleTestCase

from weather.serializers import (
    DailyWeatherInputSerializer,
    DailyWeatherOutputSerializer,
)


class DailyWeatherInputSerializerTests(SimpleTestCase):
    def test_valid_first_call_without_events(self):
        '''
        Verifica che la prima chiamata sia valida anche senza events.
        '''
        payload = {
            "doy": 126,
            "temperature": 15.94,
            "bagnatura": 1,
            "humidity": 97.25,
            "rain": 0.0,
        }

        serializer = DailyWeatherInputSerializer(data=payload)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["doy"], 126)
        self.assertEqual(serializer.validated_data["bagnatura"], 1)
        # Verifica che events venga impostato automaticamente a lista vuota
        self.assertEqual(serializer.validated_data["events"], [])

    def test_valid_next_call_with_events(self):
        '''
        Verifica che una chiamata successiva con events sia valida.
        Verifica inoltre che il primo dato generato in events sia:
            {
                "index": 0,
                "X": 0.0,
            }
        '''
        payload = {
            "doy": 127,
            "temperature": 17.15,
            "bagnatura": 1,
            "humidity": 42.35,
            "rain": 0.0,
            "events": [
                {
                    "index": 0,
                    "X": 0.0,
                }
            ],
        }

        serializer = DailyWeatherInputSerializer(data=payload)
        # se il test fallisce, Django/Python mostra anche il motivo della validazione fallita
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["events"][0]["index"], 0)
        self.assertEqual(serializer.validated_data["events"][0]["X"], 0.0)

    def test_invalid_doy_greater_than_366(self):
        '''
        Testa fallimento validazione con giorno invalido.
        '''
        payload = {
            "doy": 367,
            "temperature": 15.94,
            "bagnatura": 1,
            "humidity": 97.25,
            "rain": 0.0,
        }

        serializer = DailyWeatherInputSerializer(data=payload)

        # Non metto serializer.errors perchè mi aspetto che il serializer non sia valido. In caso di serializer
        # valido serializer.errors sarebbe vuoto quindi inutile da passare 
        self.assertFalse(serializer.is_valid())
        # verifica che l’errore sia stato associato al campo corretto "doy".
        self.assertIn("doy", serializer.errors)

    def test_invalid_bagnatura_value(self):
        payload = {
            "doy": 126,
            "temperature": 15.94,
            "bagnatura": 2,
            "humidity": 97.25,
            "rain": 0.0,
        }

        serializer = DailyWeatherInputSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        # verifica che l’errore sia stato associato al campo corretto "bagnatura".
        self.assertIn("bagnatura", serializer.errors)

    def test_invalid_humidity_greater_than_100(self):
        payload = {
            "doy": 126,
            "temperature": 15.94,
            "bagnatura": 1,
            "humidity": 120.0,
            "rain": 0.0,
        }

        serializer = DailyWeatherInputSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("humidity", serializer.errors)

    def test_invalid_negative_rain(self):
        payload = {
            "doy": 126,
            "temperature": 15.94,
            "bagnatura": 1,
            "humidity": 97.25,
            "rain": -1.0,
        }

        serializer = DailyWeatherInputSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("rain", serializer.errors)

    def test_invalid_x_greater_than_1(self):
        payload = {
            "doy": 127,
            "temperature": 17.15,
            "bagnatura": 1,
            "humidity": 42.35,
            "rain": 0.0,
            "events": [
                {
                    "index": 0,
                    "X": 1.5,
                }
            ],
        }

        serializer = DailyWeatherInputSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("events", serializer.errors)

    def test_duplicate_event_indexes_are_not_allowed(self):
        '''
        Test evento con index duplicato
        '''
        payload = {
            "doy": 127,
            "temperature": 17.15,
            "bagnatura": 1,
            "humidity": 42.35,
            "rain": 0.0,
            "events": [
                {
                    "index": 0,
                    "X": 0.2,
                },
                {
                    "index": 0,
                    "X": 0.4,
                },
            ],
        }

        serializer = DailyWeatherInputSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("events", serializer.errors)


class DailyWeatherOutputSerializerTests(SimpleTestCase):
    def test_valid_output_payload(self):
        payload = {
            "doy": 126,
            "events": [
                {
                    "index": 0,
                    "X": 0.0,
                }
            ],
        }

        serializer = DailyWeatherOutputSerializer(data=payload)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["doy"], 126)
        self.assertEqual(serializer.validated_data["events"][0]["index"], 0)
        self.assertEqual(serializer.validated_data["events"][0]["X"], 0.0)

    def test_invalid_output_x_less_than_0(self):
        payload = {
            "doy": 126,
            "events": [
                {
                    "index": 0,
                    "X": -0.1,
                }
            ],
        }

        serializer = DailyWeatherOutputSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("events", serializer.errors)

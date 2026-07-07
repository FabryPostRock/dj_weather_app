from django.test import SimpleTestCase

from weather.serializers import (
    DailyWeatherInputSerializer,
    DailyWeatherOutputSerializer,
)

from weather.services import (
    should_create_event,
    get_next_event_index,
    create_new_event,
    grow_event,
    grow_existing_events,
    process_daily_weather,
)


################################## SERAILIZERS ##############################################
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



################################## DATA MANIPULATION ##############################################



def fixed_growth_step() -> float:
    """
    Funzione deterministica usata nei test.
    Invece di usare random.choice(), restituisce sempre 0.2.
    """
    return 0.2


class WeatherServicesTests(SimpleTestCase):
    def test_should_create_event_with_leaf_wetness_and_rain(self):
        payload = {
            "doy": 126,
            "temperature": 10.0,
            "bagnatura": 1,
            "humidity": 50.0,
            "rain": 5.0,
            "events": [],
        }

        result = should_create_event(payload)
        self.assertTrue(result)

    def test_should_create_event_with_leaf_wetness_humidity_and_temperature(self):
        payload = {
            "doy": 126,
            "temperature": 16.0,
            "bagnatura": 1,
            "humidity": 85.0,
            "rain": 0.0,
            "events": [],
        }

        result = should_create_event(payload)
        self.assertTrue(result)

    def test_should_not_create_event_when_conditions_are_false(self):
        payload = {
            "doy": 126,
            "temperature": 14.0,
            "bagnatura": 0,
            "humidity": 70.0,
            "rain": 0.0,
            "events": [],
        }

        result = should_create_event(payload)
        self.assertFalse(result)

    def test_get_next_event_index_when_events_are_empty(self):
        events = []
        result = get_next_event_index(events)
        self.assertEqual(result, 0)

    def test_get_next_event_index_when_events_exist(self):
        events = [
            {"index": 0, "X": 0.2},
            {"index": 1, "X": 0.4},
            {"index": 2, "X": 0.6},
        ]

        result = get_next_event_index(events)
        self.assertEqual(result, 3)

    def test_create_new_event(self):
        result = create_new_event(index=0)

        expected = {
            "index": 0,
            "X": 0.0,
        }

        self.assertEqual(result, expected)

    def test_grow_event_increases_x(self):
        event = {
            "index": 0,
            "X": 0.2,
        }

        result = grow_event(
            event=event,
            growth_step_selector=fixed_growth_step,
        )

        expected = {
            "index": 0,
            "X": 0.4,
        }

        self.assertEqual(result, expected)

    def test_grow_event_does_not_exceed_one(self):
        event = {
            "index": 0,
            "X": 0.9,
        }

        result = grow_event(
            event=event,
            growth_step_selector=fixed_growth_step,
        )

        expected = {
            "index": 0,
            "X": 1.0,
        }

        self.assertEqual(result, expected)

    def test_grow_event_remains_one_when_already_completed(self):
        event = {
            "index": 0,
            "X": 1.0,
        }

        result = grow_event(
            event=event,
            growth_step_selector=fixed_growth_step,
        )

        expected = {
            "index": 0,
            "X": 1.0,
        }

        self.assertEqual(result, expected)

    def test_grow_event_does_not_mutate_original_event(self):
        event = {
            "index": 0,
            "X": 0.2,
        }

        result = grow_event(
            event=event,
            growth_step_selector=fixed_growth_step,
        )

        self.assertEqual(event["X"], 0.2)
        self.assertEqual(result["X"], 0.4)

    def test_grow_existing_events(self):
        events = [
            {"index": 0, "X": 0.0},
            {"index": 1, "X": 0.3},
        ]

        result = grow_existing_events(
            events=events,
            growth_step_selector=fixed_growth_step,
        )

        expected = [
            {"index": 0, "X": 0.2},
            {"index": 1, "X": 0.5},
        ]

        self.assertEqual(result, expected)

    def test_process_daily_weather_creates_first_event(self):
        payload = {
            "doy": 126,
            "temperature": 16.0,
            "bagnatura": 1,
            "humidity": 85.0,
            "rain": 0.0,
            "events": [],
        }

        result = process_daily_weather(
            payload=payload,
            growth_step_selector=fixed_growth_step,
        )

        expected = {
            "doy": 126,
            "events": [
                {"index": 0, "X": 0.0},
            ],
        }

        self.assertEqual(result, expected)

    def test_process_daily_weather_updates_existing_events_without_new_event(self):
        payload = {
            "doy": 127,
            "temperature": 14.0,
            "bagnatura": 0,
            "humidity": 70.0,
            "rain": 0.0,
            "events": [
                {"index": 0, "X": 0.0},
            ],
        }

        result = process_daily_weather(
            payload=payload,
            growth_step_selector=fixed_growth_step,
        )

        expected = {
            "doy": 127,
            "events": [
                {"index": 0, "X": 0.2},
            ],
        }

        self.assertEqual(result, expected)

    def test_process_daily_weather_updates_existing_events_and_appends_new_event(self):
        payload = {
            "doy": 128,
            "temperature": 20.0,
            "bagnatura": 1,
            "humidity": 60.0,
            "rain": 10.0,
            "events": [
                {"index": 0, "X": 0.2},
            ],
        }

        result = process_daily_weather(
            payload=payload,
            growth_step_selector=fixed_growth_step,
        )

        expected = {
            "doy": 128,
            "events": [
                {"index": 0, "X": 0.4},
                {"index": 1, "X": 0.0},
            ],
        }

        self.assertEqual(result, expected)
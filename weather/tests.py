from django.test import SimpleTestCase

from weather.serializers import (
    DailyWeatherInputSerializer,
    DailyWeatherOutputSerializer,
    ForecastRequestSerializer,
    ForecastResponseSerializer,
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

################################## PROBLEMA 2 SERIALIZERS ##############################################


class ForecastRequestSerializerTests(SimpleTestCase):
    def test_valid_forecast_request_with_first_day_events(self):
        """
        Verifica che una richiesta multi-DOY valida venga accettata.

        Il primo giorno contiene events.
        I giorni successivi contengono solo dati meteo.
        """
        payload = {
            "days": [
                {
                    "doy": 275,
                    "temperature": 30.0,
                    "bagnatura": 0,
                    "humidity": 32.0,
                    "rain": 0.0,
                    "events": [
                        {"index": 0, "X": 0.7},
                        {"index": 1, "X": 0.0},
                    ],
                },
                {
                    "doy": 276,
                    "temperature": 28.0,
                    "bagnatura": 0,
                    "humidity": 30.0,
                    "rain": 0.0,
                },
                {
                    "doy": 277,
                    "temperature": 27.0,
                    "bagnatura": 1,
                    "humidity": 59.0,
                    "rain": 22.0,
                },
            ]
        }

        serializer = ForecastRequestSerializer(data=payload)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(len(serializer.validated_data["days"]), 3)

        first_day = serializer.validated_data["days"][0]

        self.assertEqual(first_day["doy"], 275)
        self.assertIn("events", first_day)
        self.assertEqual(first_day["events"][0]["index"], 0)
        self.assertEqual(first_day["events"][0]["X"], 0.7)

    def test_events_in_following_days_are_ignored(self):
        """
        Verifica che eventuali events presenti nei giorni successivi al primo
        vengano ignorati.

        Nel Problema 2 lo stato events deve entrare solo nel primo giorno
        della sequenza multi-DOY.
        """
        payload = {
            "days": [
                {
                    "doy": 275,
                    "temperature": 30.0,
                    "bagnatura": 0,
                    "humidity": 32.0,
                    "rain": 0.0,
                    "events": [
                        {"index": 0, "X": 0.7},
                    ],
                },
                {
                    "doy": 276,
                    "temperature": 28.0,
                    "bagnatura": 0,
                    "humidity": 30.0,
                    "rain": 0.0,
                    "events": [
                        {"index": 99, "X": 1.0},
                    ],
                },
            ]
        }

        serializer = ForecastRequestSerializer(data=payload)

        self.assertTrue(serializer.is_valid(), serializer.errors)

        second_day = serializer.validated_data["days"][1]

        self.assertEqual(second_day["doy"], 276)
        self.assertNotIn("events", second_day)

    def test_missing_events_on_first_day_is_invalid(self):
        """
        Verifica che il primo giorno debba obbligatoriamente contenere events.
        """
        payload = {
            "days": [
                {
                    "doy": 275,
                    "temperature": 30.0,
                    "bagnatura": 0,
                    "humidity": 32.0,
                    "rain": 0.0,
                },
                {
                    "doy": 276,
                    "temperature": 28.0,
                    "bagnatura": 0,
                    "humidity": 30.0,
                    "rain": 0.0,
                },
            ]
        }

        serializer = ForecastRequestSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("days", serializer.errors)

    def test_empty_days_list_is_invalid(self):
        """
        Verifica che la lista days non possa essere vuota.
        """
        payload = {
            "days": []
        }

        serializer = ForecastRequestSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("days", serializer.errors)

    def test_more_than_eight_days_is_invalid(self):
        """
        Verifica il limite massimo:
        1 giorno storico + massimo 7 giorni previsionali = 8 giorni totali.
        """
        days = []

        for doy in range(275, 284):
            day = {
                "doy": doy,
                "temperature": 25.0,
                "bagnatura": 0,
                "humidity": 50.0,
                "rain": 0.0,
            }

            if doy == 275:
                day["events"] = [
                    {"index": 0, "X": 0.7},
                ]

            days.append(day)

        payload = {
            "days": days
        }

        serializer = ForecastRequestSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("days", serializer.errors)

    def test_duplicate_doys_are_invalid(self):
        """
        Verifica che non siano ammessi DOY duplicati.
        """
        payload = {
            "days": [
                {
                    "doy": 275,
                    "temperature": 30.0,
                    "bagnatura": 0,
                    "humidity": 32.0,
                    "rain": 0.0,
                    "events": [
                        {"index": 0, "X": 0.7},
                    ],
                },
                {
                    "doy": 275,
                    "temperature": 28.0,
                    "bagnatura": 0,
                    "humidity": 30.0,
                    "rain": 0.0,
                },
            ]
        }

        serializer = ForecastRequestSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("days", serializer.errors)

    def test_unordered_doys_are_invalid(self):
        """
        Verifica che i DOY debbano essere ordinati in modo crescente.
        """
        payload = {
            "days": [
                {
                    "doy": 276,
                    "temperature": 28.0,
                    "bagnatura": 0,
                    "humidity": 30.0,
                    "rain": 0.0,
                    "events": [
                        {"index": 0, "X": 0.7},
                    ],
                },
                {
                    "doy": 275,
                    "temperature": 30.0,
                    "bagnatura": 0,
                    "humidity": 32.0,
                    "rain": 0.0,
                },
            ]
        }

        serializer = ForecastRequestSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("days", serializer.errors)

    def test_non_consecutive_doys_are_invalid(self):
        """
        Verifica che i DOY debbano essere consecutivi.
        """
        payload = {
            "days": [
                {
                    "doy": 275,
                    "temperature": 30.0,
                    "bagnatura": 0,
                    "humidity": 32.0,
                    "rain": 0.0,
                    "events": [
                        {"index": 0, "X": 0.7},
                    ],
                },
                {
                    "doy": 277,
                    "temperature": 27.0,
                    "bagnatura": 1,
                    "humidity": 59.0,
                    "rain": 22.0,
                },
            ]
        }

        serializer = ForecastRequestSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("days", serializer.errors)

    def test_duplicate_event_indexes_on_first_day_are_invalid(self):
        """
        Verifica che events del primo giorno non possa contenere index duplicati.
        """
        payload = {
            "days": [
                {
                    "doy": 275,
                    "temperature": 30.0,
                    "bagnatura": 0,
                    "humidity": 32.0,
                    "rain": 0.0,
                    "events": [
                        {"index": 0, "X": 0.7},
                        {"index": 0, "X": 0.2},
                    ],
                }
            ]
        }

        serializer = ForecastRequestSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("days", serializer.errors)

    def test_invalid_event_x_on_first_day_is_invalid(self):
        """
        Verifica che X degli eventi iniziali debba essere compreso tra 0 e 1.
        """
        payload = {
            "days": [
                {
                    "doy": 275,
                    "temperature": 30.0,
                    "bagnatura": 0,
                    "humidity": 32.0,
                    "rain": 0.0,
                    "events": [
                        {"index": 0, "X": 1.5},
                    ],
                }
            ]
        }

        serializer = ForecastRequestSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("days", serializer.errors)

    def test_invalid_weather_field_is_invalid(self):
        """
        Verifica che i campi meteo vengano validati anche nei giorni successivi.
        """
        payload = {
            "days": [
                {
                    "doy": 275,
                    "temperature": 30.0,
                    "bagnatura": 0,
                    "humidity": 32.0,
                    "rain": 0.0,
                    "events": [
                        {"index": 0, "X": 0.7},
                    ],
                },
                {
                    "doy": 276,
                    "temperature": 28.0,
                    "bagnatura": 2,
                    "humidity": 30.0,
                    "rain": 0.0,
                },
            ]
        }

        serializer = ForecastRequestSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("days", serializer.errors)


class ForecastResponseSerializerTests(SimpleTestCase):
    def test_valid_forecast_response(self):
        """
        Verifica che la response del Problema 2 accetti una lista di risultati
        nel formato della black-box del Problema 1: doy + events.
        """
        payload = {
            "days": [
                {
                    "doy": 275,
                    "events": [
                        {"index": 0, "X": 0.7},
                        {"index": 1, "X": 0.0},
                    ],
                },
                {
                    "doy": 276,
                    "events": [
                        {"index": 0, "X": 0.9},
                        {"index": 1, "X": 0.1},
                    ],
                },
            ]
        }

        serializer = ForecastResponseSerializer(data=payload)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(len(serializer.validated_data["days"]), 2)
        self.assertEqual(serializer.validated_data["days"][0]["doy"], 275)
        self.assertEqual(serializer.validated_data["days"][1]["events"][0]["X"], 0.9)

    def test_forecast_response_without_events_is_invalid(self):
        """
        Verifica che ogni giorno della response debba contenere events.
        """
        payload = {
            "days": [
                {
                    "doy": 275,
                }
            ]
        }

        serializer = ForecastResponseSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("days", serializer.errors)

    def test_forecast_response_with_invalid_x_is_invalid(self):
        """
        Verifica che anche la response multi-DOY rispetti il vincolo 0 <= X <= 1.
        """
        payload = {
            "days": [
                {
                    "doy": 275,
                    "events": [
                        {"index": 0, "X": 1.2},
                    ],
                }
            ]
        }

        serializer = ForecastResponseSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn("days", serializer.errors)
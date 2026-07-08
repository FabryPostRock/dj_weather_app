import random
from typing import Any, Callable
from django.db import transaction

from weather.models import ForecastDay
from weather.serializers import (
    DailyWeatherInputSerializer,
    DailyWeatherOutputSerializer,
)

Event = dict[str, int | float]
WeatherPayload = dict[str, Any]


X_MIN_VALUE = 0.0
X_MAX_VALUE = 1.0
X_INITIAL_VALUE = 0.0

X_DECIMAL_PLACES = 3

GROWTH_STEPS = (0.1, 0.2, 0.3)


def round_x(value: float) -> float:
    """
    Arrotonda X a un numero fisso di decimali.
    Questo evita risultati floating point poco leggibili, ad esempio:
    0.1 + 0.2 = 0.30000000000000004
    """

    return round(value, X_DECIMAL_PLACES)
    


def clamp_x(value: float) -> float:
    """
    Limita X all'intervallo [0, 1].
    """

    return min(max(value, X_MIN_VALUE), X_MAX_VALUE)


def should_create_event(weather_data: WeatherPayload) -> bool:
    """
    Determina se, in base ai dati meteo giornalieri, deve nascere un nuovo evento.
    Le condizioni richieste sono:
    1. bagnatura = 1 e rain > 0
    2. bagnatura = 1 e humidity > 80 e temperature > 15
    """

    bagnatura = weather_data["bagnatura"]
    rain = weather_data["rain"]
    humidity = weather_data["humidity"]
    temperature = weather_data["temperature"]

    condition_rain = bagnatura == 1 and rain > 0
    condition_humidity_temperature = (
        bagnatura == 1
        and humidity > 80
        and temperature > 15
    )

    return condition_rain or condition_humidity_temperature


def get_next_event_index(events: list[Event]) -> int:
    """
    Calcola il prossimo index disponibile.
    Se non ci sono eventi, il primo index è 0.
    Se ci sono eventi, il nuovo index è max(index) + 1.
    """

    if not events:
        return 0

    return max(event["index"] for event in events) + 1


def create_new_event(index: int) -> Event:
    """
    Crea un nuovo evento con X iniziale = 0.
    """

    return {
        "index": index,
        "X": X_INITIAL_VALUE,
    }


def choose_growth_step() -> float:
    """
    Estrae casualmente una delle tre regole additive disponibili.
    Regola A: X = X + 0.1
    Regola B: X = X + 0.2
    Regola C: X = X + 0.3
    """

    return random.choice(GROWTH_STEPS)


def grow_event(
    event: Event,
    growth_step_selector: Callable[[], float] = choose_growth_step,
) -> Event:
    """
    Aggiorna il valore X di un singolo evento.

    La funzione:
    - non modifica direttamente il dizionario ricevuto in input;
    - se X è già 1, lo lascia a 1;
    - altrimenti sceglie casualmente uno step di crescita;
    - limita sempre il risultato a X <= 1.
    """

    current_x = float(event["X"])

    if current_x >= X_MAX_VALUE:
        new_x = X_MAX_VALUE
    else:
        growth_step = growth_step_selector()
        new_x = clamp_x(current_x + growth_step)
        new_x = round_x(new_x)

    return {
        "index": event["index"],
        "X": new_x,
    }


def grow_existing_events(
    events: list[Event],
    growth_step_selector: Callable[[], float] = choose_growth_step,
) -> list[Event]:
    """
    Aggiorna tutti gli eventi già esistenti.
    """

    return [
        grow_event(
            event=event,
            growth_step_selector=growth_step_selector,
        )
        for event in events
    ]


def process_daily_weather(
    payload: WeatherPayload,
    growth_step_selector: Callable[[], float] = choose_growth_step,
) -> dict[str, Any]:
    """
    Funzione principale del Problema 1.

    Flusso:
    1. riceve dati meteo giornalieri + eventuali events precedenti;
    2. aggiorna X degli eventi già esistenti;
    3. valuta se creare un nuovo evento;
    4. restituisce doy + events aggiornati.

    Nota:
    il nuovo evento, quando creato, viene accodato con X = 0.0.
    Non cresce nella stessa iterazione in cui nasce.
    """

    previous_events = payload.get("events", [])

    updated_events = grow_existing_events(
        events=previous_events,
        growth_step_selector=growth_step_selector,
    )

    if should_create_event(payload):
        next_index = get_next_event_index(updated_events)
        new_event = create_new_event(next_index)
        updated_events.append(new_event)

    return {
        "doy": payload["doy"],
        "events": updated_events,
    }


############################################### MULTI-DAY ####################################################


def process_multi_day_weather(payload: WeatherPayload) -> dict[str, Any]:
    """
    Chiama la logica del Problema 1 trattandola come black-box.

    Il Problema 2 conosce solo:
    - il formato JSON di input del Problema 1;
    - il formato JSON di output del Problema 1.

    Non usa direttamente le funzioni interne di crescita/creazione evento.
    """

    input_serializer = DailyWeatherInputSerializer(data=payload)
    input_serializer.is_valid(raise_exception=True)

    result = process_daily_weather(input_serializer.validated_data)

    output_serializer = DailyWeatherOutputSerializer(data=result)
    output_serializer.is_valid(raise_exception=True)

    return output_serializer.validated_data



def save_forecast_day_result(
    weather_day: dict[str, Any],
    result: dict[str, Any],
) -> ForecastDay:
    """
    Salva nel DB il risultato prodotto per un singolo DOY.

    Il campo events rappresenta lo stato finale degli eventi alla fine
    del giorno elaborato.
    """

    forecast_day, _created = ForecastDay.objects.update_or_create(
        doy=result["doy"],
        defaults={
            "temperature": weather_day["temperature"],
            "bagnatura": weather_day["bagnatura"],
            "humidity": weather_day["humidity"],
            "rain": weather_day["rain"],
            "events": result["events"],
            "processed": True,
        },
    )

    return forecast_day


 

# Esegue tutto il codice dentro questa funzione come un’unica transazione database.
@transaction.atomic
def process_oidio_forecast_days(
    weather_days: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Funzione principale del Problema 2.

    Riceve una sequenza multi-DOY già validata dal ForecastRequestSerializer.

    Regole:
    - il primo giorno contiene events, cioè lo stato antecedente alla sequenza;
    - per ogni giorno viene costruito il payload compatibile con il Problema 1;
    - il Problema 1 viene chiamato come black-box;
    - il risultato di ogni giorno viene salvato in ForecastDay;
    - se un giorno è già processed=True, non viene ricalcolato.
    """

    results = []

    current_events = weather_days[0]["events"]

    for weather_day in weather_days:
        doy = weather_day["doy"]

        existing_forecast_day = (
            ForecastDay.objects
            .filter(doy=doy, processed=True)
            .first()
        )

        if existing_forecast_day is not None:
            # Converte un record ForecastDay nel formato pubblico di output:
            result =  {
                        "doy": existing_forecast_day.doy,
                        "events": existing_forecast_day.events,
                    }
            current_events = result["events"]
            results.append(result)
            continue

        # WeatherPayload object 
        # - weather_day contiene i dati meteo del giorno corrente.
        # - previous_events contiene lo stato eventi del giorno precedente.
        problem_1_payload = {
                "doy": weather_day["doy"],
                "temperature": weather_day["temperature"],
                "bagnatura": weather_day["bagnatura"],
                "humidity": weather_day["humidity"],
                "rain": weather_day["rain"],
                "events": current_events,
            }
        result = process_multi_day_weather(problem_1_payload)

        save_forecast_day_result(
            weather_day=weather_day,
            result=result,
        )

        current_events = result["events"]
        results.append(result)

    return {
        "days": results,
    }
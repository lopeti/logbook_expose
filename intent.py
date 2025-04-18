# custom_components/your_integration/intent.py

from homeassistant.helpers import intent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.intent import IntentHandler, IntentResponse
from homeassistant.helpers.template import Template
from homeassistant.util.dt import parse_datetime


INTENT_TYPE = "LBEQueryLogbook"


class LBEQueryLogbookHandler(IntentHandler):
    intent_type = INTENT_TYPE

    async def async_handle(self, intent_obj):
        hass: HomeAssistant = intent_obj.hass
        slots = intent_obj.slots

        # Paraméterek kinyerése
        time_period = slots.get("time_period", {}).get("value", "last 1 hour")
        start_time = slots.get("start_time", {}).get("value", "")
        end_time = slots.get("end_time", {}).get("value", "")
        area = slots.get("area", {}).get("value", "")
        entity = slots.get("entity", {}).get("value", "")
        domain = slots.get("domain", {}).get("value", "")
        device_class = slots.get("device_class", {}).get("value", "")
        state = slots.get("state", {}).get("value", "")

        # Lekérdezés szöveg dinamikusan
        if start_time and end_time:
            query = f"What happened between {start_time} and {end_time}?"
        elif entity and area:
            query = f"What happened with the {entity} in the {area} in the {time_period}?"
        elif entity:
            query = f"What happened with the {entity} in the {time_period}?"
        elif area:
            query = f"What happened in the {area} in the {time_period}?"
        else:
            query = f"What happened in the {time_period}?"

        # Szolgáltatás meghívása
        await hass.services.async_call(
            "logbook_expose",
            "log_query",
            {
                "question": query,
                "question_type": "custom_query",
                "time_period": time_period,
                "start_time": start_time,
                "end_time": end_time,
                "area": area,
                "entity": entity,
                "domain": domain,
                "device_classes": device_class,
                "state": state,
            },
            blocking=True,
        )

        # Válasz összeállítása
        log_result = hass.states.get("logbook_expose.last_result")
        if log_result and "logbook" in log_result.attributes:
            log_output = log_result.attributes["logbook"]
        else:
            log_output = "no events found."

        response = intent_obj.create_response()
        response.async_set_speech(f"The log query result:\n{log_output}")
        return response

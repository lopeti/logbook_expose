import logging
import subprocess
import os
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry

# Import dependencies from the local directory
from .log_query import log_query
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Ensure the log and response directories exist
script_dir = os.path.dirname(__file__)
log_dir = os.path.join(script_dir, "log")
response_dir = os.path.join(script_dir, "response")
os.makedirs(log_dir, exist_ok=True)
os.makedirs(response_dir, exist_ok=True)

async def run_log_query(hass, ha_token, question, question_type, area_id, time_period, entity_id, domain, device_class, state):
    """Run the log_query logic and return the result."""
    try:
        return await log_query(hass, ha_token, question, question_type, area_id, time_period, entity_id, domain, device_class, state)
    except Exception as e:
        _LOGGER.error("Error running log_query logic: %s", e)
        return "Error: Unable to process the log query."

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the logbook_expose integration."""
    ha_token = config.get("ha_token", None)
    enable_file_logging = config.get("enable_file_logging", False)

    async def handle_log_query(call: ServiceCall):
        """Handle the log_query service call."""
        question = call.data.get("question", "")
        question_type = call.data.get("question_type", "all_events_now")
        area_id = call.data.get("area_id", "")
        time_period = call.data.get("time_period", "now")
        entity_id = call.data.get("entity_id", "")
        domain = call.data.get("domain", "")
        device_class = call.data.get("device_class", "")
        state = call.data.get("state", "")

        result = await run_log_query(hass, ha_token, question, question_type, area_id, time_period, entity_id, domain, device_class, state)
        hass.states.async_set(
            "logbook_expose.last_result",
            "ok",  # Set a short state value
            {
                "question": question,
                "question_type": question_type,
                "area_id": area_id,
                "time_period": time_period,
                "entity_id": entity_id,
                "domain": domain,
                "device_class": device_class,
                "state": state,
                "logbook": result,  # Store the log result in attributes
            }
        )

    hass.services.async_register("logbook_expose", "log_query", handle_log_query)
    _LOGGER.info("Registered log_query service with set_logbook_expose trigger.")

    if enable_file_logging:
        _LOGGER.info("File logging is enabled.")
    else:
        _LOGGER.info("File logging is disabled.")

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up logbook_expose from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    async def handle_log_query(call: ServiceCall):
        """Handle the log_query service call."""
        question = call.data.get("question", "")
        question_type = call.data.get("question_type", "all_events_now")
        area_id = call.data.get("area_id", "")
        time_period = call.data.get("time_period", "now")
        entity_id = call.data.get("entity_id", "")
        domain = call.data.get("domain", "")
        device_class = call.data.get("device_class", "")
        state = call.data.get("state", "")

        result = await run_log_query(hass, entry.data.get("ha_token"), question, question_type, area_id, time_period, entity_id, domain, device_class, state)
        hass.states.async_set(
            "logbook_expose.last_result",
            "ok",  # Set a short state value
            {
                "question": question,
                "question_type": question_type,
                "area_id": area_id,
                "time_period": time_period,
                "entity_id": entity_id,
                "domain": domain,
                "device_class": device_class,
                "state": state,
                "logbook": result,  # Store the log result in attributes
            }
        )

    hass.services.async_register(DOMAIN, "log_query", handle_log_query)
    _LOGGER.info("Registered log_query service with set_logbook_expose trigger.")

    return True
import logging
import subprocess
import os
import yaml
import shutil
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import intent

# Import dependencies from the local directory
from .log_query import log_query
from .const import DOMAIN, TIME_PERIODS

_LOGGER = logging.getLogger(__name__)

# Ensure the log and response directories exist
script_dir = os.path.dirname(__file__)
log_dir = os.path.join(script_dir, "log")
response_dir = os.path.join(script_dir, "response")
os.makedirs(log_dir, exist_ok=True)
os.makedirs(response_dir, exist_ok=True)

async def run_log_query(hass, ha_token, question, question_type, area_id, time_period, entity_id, domain, device_class, state, char_limit):
    """Run the log_query logic and return the result."""
    # Replace hardcoded valid_time_periods with TIME_PERIODS from const.py
    if time_period not in TIME_PERIODS:
        _LOGGER.error("Invalid time_period value: %s", time_period)
        return "Error: Invalid time_period value."

    try:
        result = await log_query(hass, ha_token, question, question_type, area_id, time_period, entity_id, domain, device_class, state, char_limit)
        return result
    except Exception as e:
        _LOGGER.error("Error running log_query logic: %s", e)
        return "Error: Unable to process the log query."

def copy_intent_script(hass: HomeAssistant):
    """Copy the intent script file to the intent_scripts directory."""
    try:
        source_file = os.path.join(script_dir, "logbook_expose_intent_scripts.yaml")
        config_dir = hass.config.config_dir
        dest_dir = os.path.join(config_dir, "intent_scripts")
        dest_file = os.path.join(dest_dir, "logbook_expose_intent_scripts.yaml")

        os.makedirs(dest_dir, exist_ok=True)

        if os.path.exists(source_file):
            shutil.copy2(source_file, dest_file)
            _LOGGER.info(f"Successfully copied {source_file} to {dest_file}")
        else:
            _LOGGER.warning(f"Source file {source_file} does not exist, could not copy to intent_scripts directory")
    except Exception as e:
        _LOGGER.error(f"Error copying intent scripts file: {e}")

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the logbook_expose integration."""
    ha_token = config.get("ha_token", None)
    enable_file_logging = config.get("enable_file_logging", False)
    
    # Copy intent scripts file to the intent_scripts directory
    copy_intent_script(hass)

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

        result = await run_log_query(hass, ha_token, question, question_type, area_id, time_period, entity_id, domain, device_class, state, config.get("char_limit", 262144))
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

    copy_intent_script(hass)

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

        result = await run_log_query(hass, entry.data.get("ha_token"), question, question_type, area_id, time_period, entity_id, domain, device_class, state, entry.options.get("char_limit", 262144))
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

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reload logbook_expose from a config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

    copy_intent_script(hass)
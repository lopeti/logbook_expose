import logging
import subprocess
import os
import yaml
import shutil
import aiofiles
import asyncio
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import intent
from .intent import LBEQueryLogbookHandler

# Import dependencies from the local directory
from .const import DOMAIN
#import dependencies from logbook_processor
from .logbook_processor.query import run_log_query as log_query
_LOGGER = logging.getLogger(__name__)

# Ensure the log and response directories exist
script_dir = os.path.dirname(__file__)
log_dir = os.path.join(script_dir, "log")
response_dir = os.path.join(script_dir, "response")
os.makedirs(log_dir, exist_ok=True)
os.makedirs(response_dir, exist_ok=True)

async def run_log_query(hass, ha_token, question, question_type, area, time_period, entity, domain, device_classes, state, char_limit, start_time, end_time):
    """Run the log_query logic and return the result."""

    try:
        result = await log_query(hass, ha_token, question, question_type, area, time_period, entity, domain, device_classes, state, char_limit, start_time, end_time)
        return result
    except Exception as e:
        _LOGGER.error("Error running log_query logic: %s", e)
        return "Error: Unable to process the log query."

async def copy_intent_script(hass: HomeAssistant):
    """Copy the intent script file to the intent_scripts directory asynchronously."""
    try:
        source_file = os.path.join(script_dir, "logbook_expose_intent_scripts.yaml")
        config_dir = hass.config.config_dir
        dest_dir = os.path.join(config_dir, "intent_scripts")
        dest_file = os.path.join(dest_dir, "logbook_expose_intent_scripts.yaml")

        os.makedirs(dest_dir, exist_ok=True)

        if os.path.exists(source_file):
            async with aiofiles.open(source_file, 'rb') as src, aiofiles.open(dest_file, 'wb') as dst:
                while True:
                    chunk = await src.read(1024 * 1024)  # Read in chunks of 1MB
                    if not chunk:
                        break
                    await dst.write(chunk)
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
    await copy_intent_script(hass)

    async def handle_log_query(call: ServiceCall):
        """Handle the log_query service call."""
        question = call.data.get("question", "")
        question_type = call.data.get("question_type", "all_events_now")
        area = call.data.get("area", "")
        time_period = call.data.get("time_period", "now")
        entity = call.data.get("entity", "")
        domain = call.data.get("domain", "")
        device_classes = call.data.get("device_classes", "")
        state = call.data.get("state", "")
        start_time = call.data.get("start_time", "")
        end_time = call.data.get("end_time", "")

        result = await run_log_query(hass, ha_token, question, question_type, area, time_period, entity, domain, device_classes, state, config.get("char_limit", 262144), start_time, end_time)
        hass.states.async_set(
            "logbook_expose.last_result",
            "ok",  # Set a short state value
            {
                "question": question,
                "question_type": question_type,
                "area": area,
                "time_period": time_period,
                "entity": entity,
                "domain": domain,
                "device_classes": device_classes,
                "state": state,
                "logbook": result,  # Store the log result in attributes
                "start_time": start_time,
                "end_time": end_time,
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

    #await copy_intent_script(hass)
    hass.helpers.intent.async_register(LBEQueryLogbookHandler())
    
    async def handle_log_query(call: ServiceCall):
        """Handle the log_query service call."""
        question = call.data.get("question", "")
        question_type = call.data.get("question_type", "all_events_now")
        area = call.data.get("area", "")
        time_period = call.data.get("time_period")
        entity = call.data.get("entity", "")
        domain = call.data.get("domain", "")
        device_classes = call.data.get("device_classes", "")
        state = call.data.get("state", "")
        start_time = call.data.get("start_time", "")
        end_time = call.data.get("end_time", "")

        result = await run_log_query(hass, entry.data.get("ha_token"), question, question_type, area, time_period, entity, domain, device_classes, state, entry.options.get("char_limit", 262144), start_time, end_time)
        hass.states.async_set(
            "logbook_expose.last_result",
            "ok",  # Set a short state value
            {
                "question": question,
                "question_type": question_type,
                "area": area,
                "time_period": time_period,
                "start_time": start_time,
                "end_time": end_time,
                "entity": entity,
                "domain": domain,
                "device_classes": device_classes,
                "state": state,
                "logbook": result,  # Store the log result in attributes
                "start_time": start_time,
                "end_time": end_time,
            }
        )

    hass.services.async_register(DOMAIN, "log_query", handle_log_query)
    _LOGGER.info("Registered log_query service with set_logbook_expose trigger.")

    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reload logbook_expose from a config entry."""
    # Unload the entry if it exists
    await hass.config_entries.async_unload(entry.entry_id)
    await async_setup_entry(hass, entry)

    await copy_intent_script(hass)
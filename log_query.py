import aiohttp
import logging
from datetime import datetime, timedelta, timezone
import pytz
import re
import os
import asyncio

# Import the format_events function
from .event_formatter import format_events

_LOGGER = logging.getLogger(__name__)

# Ensure the log and response directories exist
script_dir = os.path.dirname(__file__)  # Current directory (log_qa)
log_dir = os.path.join(script_dir, "log")
response_dir = os.path.join(script_dir, "response")
os.makedirs(log_dir, exist_ok=True)
os.makedirs(response_dir, exist_ok=True)

# Initialize Budapest timezone outside of async functions
BUDAPEST_TZ = pytz.timezone("Europe/Budapest")

async def log_to_file(filename, content):
    """Helper function to log content to a file."""
    file_path = os.path.join(log_dir, filename)
    with open(file_path, "w", encoding="utf-8") as log_file:
        log_file.write(content)

async def map_device_classes(hass):
    """Fetch entity attributes and map device classes."""
    entity_states = hass.states.async_all()
    device_class_map = {}

    for state in entity_states:
        entity_id = state.entity_id
        device_class = state.attributes.get("device_class")
        if device_class:
            device_class_map[entity_id] = device_class

    return device_class_map

async def log_query(hass, ha_token, question, question_type, area_name_or_alias=None, time_period=None, entity_id=None, domain=None, device_class=None, state=None, char_limit=None):
    _LOGGER.debug("log_query called with parameters: question=%s, question_type=%s, area_name_or_alias=%s, time_period=%s, entity_id=%s, domain=%s, device_class=%s, state=%s",
                  question, question_type, area_name_or_alias, time_period, entity_id, domain, device_class, state)

    # Ensure only valid time_period values are handled
    from .const import TIME_PERIODS

    if time_period not in TIME_PERIODS:
        _LOGGER.error("Invalid time_period value: %s", time_period)
        return [f"Error: Invalid time_period value: {time_period}"]

    # Retrieve home_assistant_url from Home Assistant configuration
    home_assistant_url = hass.config.internal_url or hass.config.external_url
    base_url = f"{home_assistant_url}/api/logbook"
    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json"
    }

    # Fetch area mappings and entity registry data directly using Home Assistant's registry objects
    async def fetch_area_mappings():
        try:
            area_registry = hass.data.get("area_registry")
            if area_registry:
                areas = list(area_registry.areas.values())
                if not areas:
                    _LOGGER.warning("No areas found in area_registry.")
                # Access attributes directly instead of using .get()
                return [{"area_id": area.id, "name": area.name, "aliases": area.aliases if hasattr(area, "aliases") else []} for area in areas]
            else:
                _LOGGER.warning("Area registry not available in hass.data.")
                return []
        except Exception as e:
            _LOGGER.error("Error fetching area mappings: %s", e)
            return []

    # Fetch entity registry data
    async def fetch_entity_mappings():
        try:
            entity_registry = hass.data.get("entity_registry")
            if entity_registry:
                # Get entity registry entries directly
                entities = list(entity_registry.entities.values())
                
                # Create separate dictionaries for device_class and friendly_name
                device_class_map = {}
                friendly_name_map = {}
                
                for entity_id in [entity.entity_id for entity in entities]:
                    state = hass.states.get(entity_id)
                    if state:
                        if "device_class" in state.attributes:
                            device_class_map[entity_id] = state.attributes["device_class"]
                        if "friendly_name" in state.attributes:
                            friendly_name_map[entity_id] = state.attributes["friendly_name"]
                
                _LOGGER.debug("Fetched device classes for %s entities", len(device_class_map))
                _LOGGER.debug("Fetched friendly names for %s entities", len(friendly_name_map))
                return device_class_map, friendly_name_map
            else:
                _LOGGER.warning("Entity registry not available")
                return {}, {}
        except Exception as e:
            _LOGGER.error("Error fetching entity mappings: %s", e)
            return {}, {}

    # Fetch area and entity mappings
    area_mappings = await fetch_area_mappings()
    if not area_mappings:
        _LOGGER.error("Area mappings are empty. Please check the area registry configuration.")
        return [f"Error: No areas found in the area registry."]

    device_class_mappings, friendly_name_mappings = await fetch_entity_mappings()
    
    # Update logging to show the correct type
    _LOGGER.debug("Device class mappings type: %s with %d entries", type(device_class_mappings), len(device_class_mappings))
    _LOGGER.debug("Friendly name mappings type: %s with %d entries", type(friendly_name_mappings), len(friendly_name_mappings))
    _LOGGER.debug("Device class mappings sample: %s", dict(list(device_class_mappings.items())[:5]))  # Show first 5 items
    _LOGGER.debug("Friendly name mappings sample: %s", dict(list(friendly_name_mappings.items())[:5]))  # Show first 5 items
    _LOGGER.debug("Area mappings type: %s with %d entries", type(area_mappings), len(area_mappings))

    # Create a mapping of area_id to area name and aliases
    area_id_to_name = {}
    area_alias_to_id = {}
    if isinstance(area_mappings, list):
        for area_item in area_mappings:
            if isinstance(area_item, dict) and "area_id" in area_item and "name" in area_item:
                area_id_to_name[area_item["area_id"]] = area_item["name"].lower()
                for alias in area_item.get("aliases", []):
                    area_alias_to_id[alias.lower()] = area_item["area_id"]
    else:
        _LOGGER.warning("Unexpected format for area mappings: %s", type(area_mappings))

    # Combine area names and aliases into a single lookup
    area_name_to_id = {**area_id_to_name, **area_alias_to_id}

    # Convert area_name_or_alias to a list of area IDs
    area_ids = set()
    if area_name_or_alias:
        # Split area_name_or_alias by commas and normalize to lowercase
        area_names_or_aliases = [name.strip().lower() for name in area_name_or_alias.split(',')]
        _LOGGER.debug("Filtering for multiple areas (names or aliases): %s", area_names_or_aliases)

        # Map area names or aliases to area IDs using area_name_to_id
        for area in area_names_or_aliases:
            if area in area_name_to_id:
                resolved_area_id = area_name_to_id[area]
                area_ids.add(resolved_area_id)
                _LOGGER.debug("Resolved '%s' to area_id '%s'", area, resolved_area_id)
            else:
                _LOGGER.warning("Area name or alias '%s' could not be resolved to an area ID.", area)

        _LOGGER.debug("Final resolved area IDs for filtering: %s", area_ids)

    # Időintervallum kiszámítása
    now = datetime.now(timezone.utc)
    _LOGGER.debug("Current UTC time: %s", now)

    if time_period == "today":
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_period == "yesterday":
        start_time = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1)
    elif time_period == "last_hour":
        start_time = now - timedelta(hours=1)
    elif time_period == "last_3_hours":
        start_time = now - timedelta(hours=3)
    elif time_period == "last_5_hours":
        start_time = now - timedelta(hours=5)
    elif time_period == "last_8_hours":
        start_time = now - timedelta(hours=8)
    elif time_period == "last_12_hours":
        start_time = now - timedelta(hours=12)
    elif time_period == "last_24h":
        start_time = now - timedelta(hours=24)
    elif time_period.startswith("last_") and time_period.endswith("_minutes"):
        try:
            minutes = int(time_period.split("_")[1])
            start_time = now - timedelta(minutes=minutes)
        except ValueError:
            _LOGGER.error("Invalid time_period value: %s", time_period)
            return [f"Error: Invalid time_period value: {time_period}"]
    else:
        start_time = now - timedelta(minutes=60)  # Alapértelmezett: utolsó 60 perc
    end_time = now

    _LOGGER.debug("Calculated time range: start_time=%s, end_time=%s", start_time, end_time)

    # Időformátumok
    start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    _LOGGER.debug("Formatted time range: start_time_str=%s, end_time_str=%s", start_time_str, end_time_str)

    # API hívás
    params = {"end_time": end_time_str}
    if entity_id:
        params["entity_id"] = entity_id
    api_url = f"{base_url}/{start_time_str}"
    _LOGGER.debug("API URL: %s, Params: %s", api_url, params)

    # Tracking counters for debugging
    total_entries = 0
    filtered_entries = 0
    area_filtered = 0
    entity_filtered = 0
    domain_filtered = 0
    device_class_filtered = 0
    state_filtered = 0
    ignore_filtered = 0

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers, params=params) as response:
                _LOGGER.debug("API response status: %s", response.status)
                if response.status != 200:
                    return [f"Hiba a logok lekérdezése során: {response.status}"]
                logbook_data = await response.json()
                _LOGGER.debug("API logbook data length: %d entries", len(logbook_data))
                # Log a few entries to debug
                if len(logbook_data) > 0:
                    _LOGGER.debug("First few logbook entries: %s", logbook_data[:3])
                else:
                    _LOGGER.warning("No logbook entries returned from API")

    except Exception as e:
        _LOGGER.error("Error during API call: %s", e)
        return [f"Hiba a logok lekérdezése során: {e}"]

    # Define ignored entities list
    ignored_entities = ["sensor.date_time"]

    # Prepare structured events for formatting
    structured_events = []
    last_event = None
    total_entries = len(logbook_data)
    filtered_entries = 0
    duplicate_entries = 0
    
    # Process logbook entries
    for entry in logbook_data:
        entry_entity_id = entry.get("entity_id", "")
        entry_state = entry.get("state", "")
        entry_when = entry.get("when", "")

        # Check if the entity has conversation expose option set to True
        entity_registry = hass.data.get("entity_registry")
        if entity_registry:
            entity_entry = entity_registry.entities.get(entry_entity_id)
            if entity_entry:
                expose_option = entity_entry.options.get("conversation", {}).get("should_expose", False)
                if not expose_option:
                    _LOGGER.debug("Skipping entity '%s' because conversation expose option is not True", entry_entity_id)
                    ignore_filtered += 1
                    continue
            else:
                _LOGGER.debug("Entity '%s' not found in entity_registry", entry_entity_id)
        else:
            _LOGGER.warning("Entity registry not available in hass.data")
            
# binary_sensor.bejarat_motion_detected - if we detected this device, just take a log from it
        if entry_entity_id == "binary_sensor.bejarat_motion_detected":
            _LOGGER.debug("Found entry for binary_sensor.bejarat_motion_detected, using its state")

        # Skip ignored entities
        if entry_entity_id in ignored_entities:
            ignore_filtered += 1
            continue

        # Időbélyeg konvertálása helyi időre
        try:
            utc_time = datetime.fromisoformat(entry_when.replace("Z", "+00:00"))
            local_time = utc_time.astimezone(BUDAPEST_TZ)
            formatted_time = local_time.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            _LOGGER.warning("Invalid timestamp format: %s", entry_when)
            continue

        # Filter by area IDs
        if area_ids:
            # Fetch the actual area_id of the entity from the entity registry
            actual_area_id = None
            entity_registry = hass.data.get("entity_registry")
            device_registry = hass.data.get("device_registry")
            if entity_registry:
                entity_entry = entity_registry.entities.get(entry_entity_id)
                if entity_entry:
                    actual_area_id = entity_entry.area_id
                    if not actual_area_id and entity_entry.device_id and device_registry:
                        device_entry = device_registry.devices.get(entity_entry.device_id)
                        if device_entry:
                            actual_area_id = device_entry.area_id
                            #_LOGGER.debug("Fetched area_id '%s' from device_registry for entity '%s'", actual_area_id, entry_entity_id)
                else:
                    _LOGGER.debug("Entity '%s' not found in entity_registry", entry_entity_id)
            else:
                _LOGGER.warning("Entity registry not available in hass.data")

            # Check if the actual area_id matches any of the resolved area IDs
            if actual_area_id and actual_area_id in area_ids:
                _LOGGER.debug("Entity '%s' matches area_id '%s'", entry_entity_id, actual_area_id)
            else:
                #_LOGGER.debug("Entity '%s' with actual_area_id '%s' does not match any area_id in %s", entry_entity_id, actual_area_id, area_ids)
                area_filtered += 1
                continue

        if entity_id and entity_id != entry_entity_id:
            entity_filtered += 1
            continue
        if domain and not entry_entity_id.startswith(f"{domain}."):
            domain_filtered += 1
            continue
        if device_class and device_class != entry.get("attributes", {}).get("device_class", ""):
            device_class_filtered += 1
            continue
        if state and state != entry_state:
            state_filtered += 1
            continue

        # Fetch device_class from device_class_mappings if available
        device_class_value = entry.get("attributes", {}).get("device_class", "")
        if not device_class_value and entry_entity_id in device_class_mappings:
            device_class_value = device_class_mappings[entry_entity_id]
            _LOGGER.debug("Found device_class '%s' for entity %s in device_class_mappings", device_class_value, entry_entity_id)

        # Fetch friendly name from various sources
        friendly_name = None
        
        # Try to get from entry name first
        if entry.get("name"):
            friendly_name = entry.get("name")
        # Then try from attributes
        elif entry.get("attributes", {}).get("friendly_name"):
            friendly_name = entry.get("attributes", {}).get("friendly_name")
        # If not found, try to get it from hass states
        else:
            state_obj = hass.states.get(entry_entity_id)
            if state_obj:
                friendly_name = state_obj.attributes.get("friendly_name", entry_entity_id)
            else:
                friendly_name = entry_entity_id
        
        _LOGGER.debug("Entity: %s, Friendly name: %s", entry_entity_id, friendly_name)

        # Create a structured event dictionary with friendly name
        current_event = {
            "timestamp": formatted_time,
            "entity_id": entry_entity_id,
            "friendly_name": friendly_name,
            "state": entry_state,
            "device_class": device_class_value,
            "event_description": generate_event_description(device_class_value, entry_state)
        }
        # skip empty device_class
        if current_event["device_class"] == "" or current_event["device_class"] == "firmware":
            device_class_filtered += 1
            continue

        # skip unknown states
        if current_event["state"] == "unknown":
            ignore_filtered += 1
            continue
        # Filter duplicate events (same second-level timestamp)
        if last_event and last_event["timestamp"][:19] == current_event["timestamp"][:19]:
            _LOGGER.debug("Skipping duplicate event with timestamp: %s", current_event["timestamp"][:19])
            continue


        # Add event to structured_events list
        structured_events.append(current_event)
        last_event = current_event

    # Log statistics
    _LOGGER.debug("Event processing statistics: Total=%d, Passed filters=%d, Area filtered=%d, Entity filtered=%d, Domain filtered=%d, Device class filtered=%d, State filtered=%d, Ignored=%d", 
                 total_entries, filtered_entries, area_filtered, entity_filtered, domain_filtered, device_class_filtered, state_filtered, ignore_filtered)
    _LOGGER.debug("Number of structured events: %d", len(structured_events))

    # Define a default character limit and validate it
    DEFAULT_CHAR_LIMIT = 262144
    if char_limit > DEFAULT_CHAR_LIMIT:
        _LOGGER.warning("Provided char_limit exceeds the maximum allowed size (%d). Using default value (%d).", DEFAULT_CHAR_LIMIT, DEFAULT_CHAR_LIMIT)
        char_limit = DEFAULT_CHAR_LIMIT

    # Add a header to the response text
    response_text = "Time, Entity, Event\n"
    for event in structured_events:
        event_text = f"{event['timestamp']}, {event['friendly_name']}, {event['event_description']}\n"
        if len(response_text) + len(event_text) > char_limit:
            _LOGGER.warning("Reached character limit of %d. Truncating response.", char_limit)
            break
        response_text += event_text

    # Return the plain text response
    return response_text



def generate_event_description(device_class, state):
    """Generate a human-readable event description based on device_class and state."""
    if device_class == "occupancy" or device_class == "motion":
        return "motion detected" if state == "on" else "motion stopped"
    elif device_class == "door":
        return "door opened" if state == "on" else "door closed"
    elif device_class == "window":
        return "window opened" if state == "on" else "window closed"
    elif device_class == "presence":
        return "presence detected" if state in ["on", "home"] else "presence stopped"
    elif device_class == "light":
        return "turned on" if state == "on" else "turned off"
    elif device_class == "lock":
        return "locked" if state == "locked" else "unlocked"
    else:
        return f"state changed to {state}"

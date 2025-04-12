import aiohttp
import logging
from datetime import datetime, timedelta, timezone
import pytz
import re
import os
import asyncio

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

async def log_query(hass, ha_token, question, question_type, area_id=None, time_period=None, entity_id=None, domain=None, device_class=None, state=None):
    """
    Lekérdezi a logokat a megadott paraméterek alapján, és minden sor elejére írja az időpontot.
    Az időbélyeg-csoportosítást csak a torlódások felismerésére használja.
    
    Args:
        question (str): A kérdés szövege.
        question_type (str): A kérdés típusa (pl. "happenings", "area_events_now").
        area_id (str): Az érintett terület neve például "konyha", "nappali"
        time_period (str): Az időszak (pl. "ma", "tegnap", "last_hour").
        entity_id (str): Az érintett entitás azonosítója.
        domain (str): Az érintett domain (pl. "light", "sensor").
        device_class (str): Az eszköz típusa.
        state (str): Az entitás állapota.
    
    Returns:
        list: A logok listája, minden sor elején az időponttal.
    """
    _LOGGER.debug("log_query called with parameters: question=%s, question_type=%s, area_id=%s, time_period=%s, entity_id=%s, domain=%s, device_class=%s, state=%s",
                  question, question_type, area_id, time_period, entity_id, domain, device_class, state)

    # Log the received area_id for debugging
    _LOGGER.debug("Received area_id: %s", area_id)

    if not area_id:
        _LOGGER.warning("No area_id provided. Please check the intent configuration.")

    # Retrieve home_assistant_url from Home Assistant configuration
    home_assistant_url = hass.config.internal_url or hass.config.external_url
    base_url = f"{home_assistant_url}/api/logbook"
    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json"
    }

    # Fetch area mappings using the /api/template endpoint
    async def fetch_area_mappings():
        area_url = f"{home_assistant_url}/api/template"
        payload = {"template": "{{ areas() }}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(area_url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        text_response = await response.text()
                        # Parse the plain text response into a Python dictionary
                        import yaml
                        return yaml.safe_load(text_response)
                    else:
                        _LOGGER.error("Failed to fetch area mappings: %s", response.status)
                        return []
        except Exception as e:
            _LOGGER.error("Error fetching area mappings: %s", e)
            return []

    # Fetch entity mappings using the /api/template endpoint
    async def fetch_entity_mappings():
        entity_url = f"{home_assistant_url}/api/template"
        payload = {"template": "{{ states | map(attribute='entity_id') | list }}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(entity_url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        text_response = await response.text()
                        # Parse the plain text response into a Python list
                        import yaml
                        return yaml.safe_load(text_response)
                    else:
                        _LOGGER.error("Failed to fetch entity mappings: %s", response.status)
                        return []
        except Exception as e:
            _LOGGER.error("Error fetching entity mappings: %s", e)
            return []

    # Fetch area and entity mappings
    area_mappings = await fetch_area_mappings()
    entity_mappings = await fetch_entity_mappings()

    # Ensure entity_mappings is a list
    if not isinstance(entity_mappings, list):
        _LOGGER.error("Unexpected format for entity mappings: %s", entity_mappings)
        return []

    # Since entity_mappings is a list of strings (entity_ids), we need a different approach
    entity_to_area = {}
    # We'll log this fact instead of trying to process entities as dictionaries
    _LOGGER.debug("Entity mappings contains %d entity IDs as strings", len(entity_mappings))
    
    # Create a mapping of area_id to area name (adjust for list format)
    area_id_to_name = {}
    if isinstance(area_mappings, list):
        for area_item in area_mappings:
            if isinstance(area_item, str):
                # If area_item is just the area name
                area_id_to_name[area_item.lower()] = area_item.lower()
            elif isinstance(area_item, dict) and "area_id" in area_item and "name" in area_item:
                # If area_item is a dictionary with area_id and name
                area_id_to_name[area_item["area_id"]] = area_item["name"].lower()
    else:
        _LOGGER.warning("Unexpected format for area mappings: %s", type(area_mappings))

    # Időintervallum kiszámítása
    now = datetime.now(timezone.utc)
    _LOGGER.debug("Current UTC time: %s", now)

    if time_period == "ma":
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_period == "tegnap":
        start_time = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1)
    elif time_period == "last_hour":
        start_time = now - timedelta(hours=1)
    elif time_period == "last_24h":
        start_time = now - timedelta(hours=24)
    elif time_period.startswith("last_") and time_period.endswith("_minutes"):
        try:
            minutes = int(time_period.split("_")[1])
            if minutes in [1, 5, 10, 15, 30]:
                start_time = now - timedelta(minutes=minutes)
            else:
                raise ValueError("Invalid minute value")
        except ValueError:
            _LOGGER.error("Invalid time_period value: %s", time_period)
            return [f"Hiba: Érvénytelen időszak: {time_period}"]
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
    api_url = f"{base_url}/{start_time_str}"
    _LOGGER.debug("API URL: %s, Params: %s", api_url, params)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers, params=params) as response:
                _LOGGER.debug("API response status: %s", response.status)
                if response.status != 200:
                    return [f"Hiba a logok lekérdezése során: {response.status}"]
                logbook_data = await response.json()
                _LOGGER.debug("API response data: %s", logbook_data[:100])

                # Log request and response to a file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                log_filename = f"log_{timestamp}.txt"
                log_content = f"Request: {params}\nResponse: {logbook_data}"
                await log_to_file(log_filename, log_content)

    except Exception as e:
        _LOGGER.error("Error during API call: %s", e)
        return [f"Hiba a logok lekérdezése során: {e}"]

    # Define ignored entities list
    ignored_entities = ["sensor.date_time"]

    # Események csoportosítása időbélyeg szerint a torlódások felismeréséhez
    grouped_events = {}
    for entry in logbook_data:
        entry_entity_id = entry.get("entity_id", "")
        entry_state = entry.get("state", "")
        entry_when = entry.get("when", "")

        # Skip ignored entities
        if entry_entity_id in ignored_entities:
            continue

        # Időbélyeg konvertálása helyi időre
        try:
            utc_time = datetime.fromisoformat(entry_when.replace("Z", "+00:00"))
            local_time = utc_time.astimezone(BUDAPEST_TZ)
            formatted_time = local_time.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            _LOGGER.warning("Invalid timestamp format: %s", entry_when)
            continue

        # Szűrés a paraméterek alapján
        if area_id:
            # Debug logging for area-based filtering
            area_name_lower = area_id.lower()
            _LOGGER.debug("Filtering for area_name_lower: %s", area_name_lower)
            _LOGGER.debug("Available area names: %s", list(area_id_to_name.values()))
            
            # More flexible area matching logic - check if any part of the name matches
            found_match = False
            for entity_name in [entry_entity_id, entry.get("name", ""), entry.get("attributes", {}).get("friendly_name", "")]:
                if area_name_lower in entity_name.lower():
                    found_match = True
                    _LOGGER.debug("Found area match in entity: %s", entity_name)
                    break
            
            if not found_match:
                continue
        if entity_id and entity_id != entry_entity_id:
            continue
        if domain and not entry_entity_id.startswith(f"{domain}."):
            continue
        if device_class and device_class not in entry.get("attributes", {}).get("device_class", ""):
            continue
        if state and state != entry_state:
            continue

        # Események csoportosítása időbélyeg szerint
        if formatted_time not in grouped_events:
            grouped_events[formatted_time] = []
        grouped_events[formatted_time].append(f"{formatted_time} {entry_entity_id:<30} {entry_state}")

    # Csoportosított események formázása
    processed_logs = []
    for timestamp, events in sorted(grouped_events.items(), reverse=True):  # Legfrissebb események előre
        if len(events) > 3:
            # Ha több mint 3 esemény van, csak egy összegző sort adjuk hozzá
            processed_logs.append(f"{timestamp} esemény torlódás (a rendszer valószínűleg újratöltötte az entitások állapotait) {len(events)} event \n")
        else:
            # Ha 3 vagy kevesebb esemény van, mindet hozzáadjuk
            processed_logs.extend(events)

    # Ensure logbook entries are properly formatted to avoid multi-line YAML issues
    formatted_logs = []
    for log in processed_logs:
        formatted_logs.append(log.replace("\n", " ").strip())

    # Convert the processed logs list into a single string with each log on a new line
    response_text = "\n".join(processed_logs)

    # Store the response in the input_text entity for the template sensor
    try:
        # Write the response to a file for the file sensor
        response_file_path = os.path.join(response_dir, "log_query_response.txt")
        with open(response_file_path, "w", encoding="utf-8") as response_file:
            response_file.write(response_text)
    except Exception as e:
        _LOGGER.error("Failed to write response to file: %s", e)

    return response_text
from datetime import datetime, timedelta, timezone
import logging
import pytz
import unicodedata
import re

_LOGGER = logging.getLogger(__name__)

# Determine local timezone dynamically from system
LOCAL_TZ = datetime.now().astimezone().tzinfo

# --- Entity Resolution ---
def resolve_entity_id_in_area(hass, user_entity_name, area_ids, domain=None, device_class=None):
    user_norm = normalize_text(user_entity_name)
    entity_registry = hass.data.get("entity_registry")
    if not entity_registry:
        _LOGGER.warning("Entity registry not available")
        return None

    for entity in entity_registry.entities.values():
        if area_ids and entity.area_id not in area_ids:
            continue

        if domain and not entity.entity_id.startswith(f"{domain}."):
            continue

        state = hass.states.get(entity.entity_id)
        if not state:
            continue

        if device_class:
            dc = state.attributes.get("device_class")
            if dc != device_class:
                continue

        friendly = state.attributes.get("friendly_name", "")
        if normalize_text(friendly) == user_norm:
            return entity.entity_id

    return None

# --- Utility Functions ---
def normalize_text(text):
    if not text:
        return ""
    normalized = unicodedata.normalize('NFD', text)
    return ''.join([c for c in normalized if unicodedata.category(c) != 'Mn']).lower()

def calculate_time_range(time_period, now, start_time_str=None, end_time_str=None):
    time_units = {
        "minutes": lambda x: timedelta(minutes=x),
        "hours": lambda x: timedelta(hours=x),
        "days": lambda x: timedelta(days=x),
    }

    if start_time_str and end_time_str:
        try:
            local_start = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=LOCAL_TZ)
            start_time = local_start.astimezone(timezone.utc)
            local_end = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=LOCAL_TZ)
            end_time = local_end.astimezone(timezone.utc)
            return start_time, end_time
        except ValueError as e:
            _LOGGER.error("Invalid start_time or end_time format: %s", e)
            return None, None

    if time_period == "today":
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now
    elif time_period == "yesterday":
        start_time = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1)
    elif time_period.endswith("days ago"):
        try:
            value = int(time_period.split(" ")[0])
            start_time = (now - timedelta(days=value)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(days=1)
        except ValueError:
            _LOGGER.error("Invalid time_period value: %s", time_period)
            return None, None
    elif time_period.startswith("last "):
        for unit, delta_func in time_units.items():
            if unit in time_period or unit[:-1] in time_period:
                try:
                    value = int(re.search(r'\d+', time_period).group())
                    start_time = now - delta_func(value)
                    end_time = now
                    break
                except ValueError:
                    _LOGGER.error("Invalid time_period value: %s", time_period)
                    return None, None
        else:
            _LOGGER.error("Invalid time_period value: %s", time_period)
            return None, None
    else:
        start_time = now - timedelta(minutes=60)
        end_time = now

    return start_time, end_time

def generate_event_description(device_class, state):
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

# --- Area Registry Access ---
def fetch_area_mappings(hass):
    try:
        area_registry = hass.data.get("area_registry")
        if area_registry:
            areas = list(area_registry.areas.values())
            if not areas:
                _LOGGER.warning("No areas found in area_registry.")
            return [
                {
                    "area_id": area.id,
                    "name": area.name,
                    "aliases": getattr(area, "aliases", [])
                }
                for area in areas
            ]
        else:
            _LOGGER.warning("Area registry not available in hass.data.")
            return []
    except Exception as e:
        _LOGGER.error("Error fetching area mappings: %s", e)
        return []

# --- Entity Registry Access ---
def fetch_entity_mappings(hass):
    try:
        entity_registry = hass.data.get("entity_registry")
        if not entity_registry:
            _LOGGER.warning("Entity registry not available")
            return {}, {}

        entities = list(entity_registry.entities.values())
        device_class_map = {}
        friendly_name_map = {}

        for entity_id in [entity.entity_id for entity in entities]:
            state = hass.states.get(entity_id)
            if state:
                device_class = state.attributes.get("device_class")
                friendly_name = state.attributes.get("friendly_name")

                if device_class:
                    device_class_map[entity_id] = device_class
                if friendly_name:
                    friendly_name_map[entity_id] = friendly_name

        return device_class_map, friendly_name_map
    except Exception as e:
        _LOGGER.error("Error fetching entity mappings: %s", e)
        return {}, {}

# --- Area Name Resolution ---
def resolve_area_ids(area_mappings, area_name_or_alias):
    area_id_to_name = {}
    area_alias_to_id = {}

    for area_item in area_mappings:
        if isinstance(area_item, dict) and "area_id" in area_item and "name" in area_item:
            area_id = area_item["area_id"]
            normalized_name = normalize_text(area_item["name"])
            area_id_to_name[area_id] = normalized_name
            area_alias_to_id[normalized_name] = area_id
            for alias in area_item.get("aliases", []):
                normalized_alias = normalize_text(alias)
                area_alias_to_id[normalized_alias] = area_id

    area_name_to_id = {**area_id_to_name, **area_alias_to_id}
    resolved_ids = set()

    if area_name_or_alias:
        names = [normalize_text(name.strip()) for name in area_name_or_alias.split(",")]
        for name in names:
            resolved_id = area_name_to_id.get(name)
            if resolved_id:
                resolved_ids.add(resolved_id)
            else:
                _LOGGER.warning("Area '%s' could not be resolved to an area ID.", name)

    return resolved_ids

# --- Logbook API Call ---
import aiohttp

async def fetch_logbook_data(hass, url, headers, params):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                _LOGGER.debug("Logbook API response status: %s", response.status)
                if response.status != 200:
                    _LOGGER.error("Failed to fetch logbook data. Status: %s", response.status)
                    return []
                return await response.json()
    except Exception as e:
        _LOGGER.error("Exception during logbook fetch: %s", e)
        return []

# --- Logbook Filtering ---
def filter_logbook_entries(entries, area_ids, entity_id=None, domain=None, device_class=None, state=None, device_class_map=None):
    filtered = []
    total_entries = len(entries)
    unknown_state_filtered = 0
    entity_id_filtered = 0
    domain_filtered = 0
    state_filtered = 0
    device_class_filtered = 0
    area_filtered = 0

    # Log the filter conditions being applied
    filter_conditions = []
    if entity_id:
        filter_conditions.append(f"entity_id='{entity_id}'")
    if domain:
        filter_conditions.append(f"domain='{domain}'")
    if state:
        filter_conditions.append(f"state='{state}'")
    if device_class:
        filter_conditions.append(f"device_class='{device_class}'")
    if area_ids:
        filter_conditions.append(f"area_ids={area_ids}")
    
    _LOGGER.debug("Applying filters: %s", ", ".join(filter_conditions) if filter_conditions else "None")

    for entry in entries:
        eid = entry.get("entity_id")
        est = entry.get("state")
        attributes = entry.get("attributes", {})

        # Skip unknown state
        if est == "unknown":
            unknown_state_filtered += 1
            continue

        # Filter by entity_id
        if entity_id and eid != entity_id:
            entity_id_filtered += 1
            continue

        # Filter by domain
        if domain and not eid.startswith(f"{domain}."):
            domain_filtered += 1
            continue

        # Filter by state
        if state and est != state:
            state_filtered += 1
            continue

        # Filter by device_class
        dc = attributes.get("device_class") or (device_class_map.get(eid) if device_class_map else None)
        if device_class and dc != device_class:
            device_class_filtered += 1
            continue

        # Filter by area_id (using pre-resolved ids in entry)
        area_ok = not area_ids or entry.get("resolved_area_id") in area_ids
        if not area_ok:
            area_filtered += 1
            continue

        filtered.append(entry)

    _LOGGER.debug("Logbook filtering stats: Total entries: %d, Passed filters: %d", total_entries, len(filtered))
    _LOGGER.debug("Filtered out: Unknown state: %d, Entity ID: %d, Domain: %d, State: %d, Device class: %d, Area: %d", 
                unknown_state_filtered, entity_id_filtered, domain_filtered, 
                state_filtered, device_class_filtered, area_filtered)

    return filtered

# --- Logbook Formatting ---
def format_logbook_entries(entries, char_limit=262144):
    output = "Time, Entity, Event"
    used = len(output)

    for entry in entries:
        try:
            utc_time = datetime.fromisoformat(entry.get("when", "").replace("Z", "+00:00"))
            local_time = utc_time.astimezone(LOCAL_TZ)
            timestamp = local_time.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            _LOGGER.warning("Invalid or missing timestamp: %s", e)
            continue

        eid = entry.get("entity_id", "unknown")
        state = entry.get("state", "")
        dc = entry.get("device_class", "")

        name = entry.get("name") or entry.get("attributes", {}).get("friendly_name") or eid
        description = generate_event_description(dc, state)
        line = f"{timestamp}, {name}, {description}"

        if used + len(line) > char_limit:
            _LOGGER.warning("Reached character limit of %d. Truncating output.", char_limit)
            break

        output += line
        used += len(line)

    return output

# --- High-Level Query Runner ---
async def run_log_query(
    hass,
    ha_token,
    question,
    question_type,
    area_name_or_alias=None,
    time_period=None,
    entity_id=None,
    domain=None,
    device_class=None,
    state=None,
    char_limit=262144,
    start_time=None,
    end_time=None
):
    _LOGGER.info("Running log query: '%s'", question)

    # Step 1: Resolve time range
    now = datetime.now(timezone.utc)
    start_dt, end_dt = calculate_time_range(time_period, now, start_time, end_time)
    if not start_dt or not end_dt:
        return "Error: Invalid time range."

    start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Step 2: Get area + entity info
    # If entity_id is a friendly name, try to resolve it based on area/domain/device_class
    if entity_id and not entity_id.startswith("sensor.") and not entity_id.startswith("binary_sensor.") and not entity_id.startswith("camera."):
        resolved = resolve_entity_id_in_area(hass, entity_id, area_ids, domain=domain, device_class=device_class)
        if resolved:
            _LOGGER.info("Resolved entity name '%s' to entity_id: %s", entity_id, resolved)
            entity_id = resolved
        else:
            _LOGGER.warning("Could not resolve entity name '%s' in given area/domain/class", entity_id)
    area_mappings = fetch_area_mappings(hass)
    area_ids = resolve_area_ids(area_mappings, area_name_or_alias)
    device_class_map, _ = fetch_entity_mappings(hass)

    # Step 3: Call logbook API
    url = f"{hass.config.internal_url or hass.config.external_url}/api/logbook/{start_str}"
    headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
    params = {"end_time": end_str}
    if entity_id:
        params["entity_id"] = entity_id
    raw_entries = await fetch_logbook_data(hass, url, headers, params)

    # Step 4: Inject resolved area_id into each entry (if available)
    for entry in raw_entries:
        resolved = None
        entity_reg = hass.data.get("entity_registry")
        device_reg = hass.data.get("device_registry")
        if entity_reg:
            ent = entity_reg.entities.get(entry.get("entity_id"))
            if ent:
                resolved = ent.area_id or (device_reg.devices.get(ent.device_id).area_id if device_reg and ent.device_id in device_reg.devices else None)
        entry["resolved_area_id"] = resolved

    # Step 5: Filter entries
    filtered = filter_logbook_entries(
        raw_entries,
        area_ids,
        entity_id=entity_id,
        domain=domain,
        device_class=device_class,
        state=state,
        device_class_map=device_class_map
    )

    # Step 6: Format final output
    return format_logbook_entries(filtered, char_limit)

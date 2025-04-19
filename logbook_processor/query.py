from datetime import datetime, timedelta, timezone
import logging
import pytz
import unicodedata
import re

_LOGGER = logging.getLogger(__name__)

# Determine local timezone dynamically from system
LOCAL_TZ = datetime.now().astimezone().tzinfo


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
        _LOGGER.debug("Resolving area_name_or_alias: %s", area_name_or_alias)  # Log the input value
        names = [normalize_text(name.strip()) for name in area_name_or_alias.split(",")]
        for name in names:
            resolved_id = area_name_to_id.get(name)
            if resolved_id:
                resolved_ids.add(resolved_id)
            else:
                _LOGGER.warning("Area '%s' could not be resolved to an area ID.", name)

    # Log the area mappings for debugging
    #_LOGGER.debug("Area mappings: %s", area_mappings)

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
def filter_logbook_entries(entries, candidate_entities, state=None, events_per_second=1, congestion="skip"):
    # Filter entries only for candidate entity_ids and matching state (if provided)
    if candidate_entities is None:
        candidate_entities = []
    if len(candidate_entities) == 0:
        _LOGGER.warning("No candidate entities provided for filtering.")
        return []

    filtered = []
    total_entries = len(entries)
    # Build a set of candidate entity_ids from the state objects
    candidate_ids = {s.entity_id for s in candidate_entities} if candidate_entities else set()
    
    last_states = {}
    for entry in entries:
        eid = entry.get("entity_id")
        est = entry.get("state")

        if est == "unknown":
            last_states[eid] = est  # Store the last state as "unknown" for this entity 
            continue
        if candidate_ids and eid not in candidate_ids:
            continue

        # Check if the state is the same as the last recorded state for this entity
        if eid in last_states and (last_states[eid] == est or last_states.get(eid) == "unknown"):
            _LOGGER.debug("Skipping entry for entity %s with state %s (last state was %s)", eid, est, last_states[eid]) 
            # If the state is the same or the last state was "unknown", skip this entry
            #but update the last state to the current one
            last_states[eid] = est #to move out from unknown state
            continue

        # Update the last state for this entity
        last_states[eid] = est

        filtered.append(entry)

    _LOGGER.debug("Logbook filtering: Total entries: %d, After candidate and state filtering: %d", total_entries, len(filtered))
    
    # Group entries by second (timestamp truncated to seconds)
    groups = {}
    for entry in filtered:
        try:
            ts = datetime.fromisoformat(entry.get("when", "").replace("Z", "+00:00")).replace(microsecond=0)
        except Exception as e:
            _LOGGER.warning("Invalid timestamp in entry: %s", e)
            continue
        groups.setdefault(ts, []).append(entry)
    
    # Apply congestion control per second group.
    result = []
    for ts in sorted(groups.keys()):
        group = groups[ts]
        if len(group) <= events_per_second:
            result.extend(group)
        else:
            if congestion == "skip":
                result.extend(group[:events_per_second])
            elif congestion == "summarize":
                # Use the first event as base and summarize the rest.
                summary = group[0].copy()
                extra = len(group) - 1
                summary_msg = f"and {extra} more events at {ts.strftime('%Y-%m-%d %H:%M:%S')}"
                # Append the summary info to the description if present.
                orig_desc = summary.get("description", "")
                summary["description"] = (orig_desc + " " if orig_desc else "") + summary_msg
                result.append(summary)
            else:
                # Unknown congestion option; fallback to no congestion handling.
                result.extend(group)
    return result

# --- Logbook Formatting ---
def format_logbook_entries(entries, char_limit=262144):
    output = "Time, Entity, Event\n"  # header with newline
    used = len(output)
    safe_char_limit = char_limit - (len(output) + 1024)  # reserve space for header
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
        device_class = entry.get("device_class", "")

        description = generate_event_description(dc, state)
        line = f"{timestamp}, {name}, {description}\n"  # add newline after each entry
        if used + len(line) > char_limit:
            _LOGGER.warning("Reached character limit of %d. Truncating output.", char_limit)
            break
        output += line
        used += len(line)
    return output

# Sample output row:
# 2025-04-17 16:38:26, Bejárati kamera, motion detected

# --- Utility: Inject Resolved Properties ---
def inject_resolved_properties(hass, entries, properties):
    for entry in entries:
        if entry.get("entity_id") == "sensor.date_time":
            continue  # Skip sensor.date_time entity

        entity_reg = hass.data.get("entity_registry")
        device_reg = hass.data.get("device_registry")
        if not entity_reg:
            continue
        ent = entity_reg.entities.get(entry.get("entity_id"))
        if not ent:
            continue
        for prop in properties:
            if prop == "area":
                resolved_area_id = ent.area_id or (device_reg.devices.get(ent.device_id).area_id if device_reg and ent.device_id in device_reg.devices else None)
                area_registry = hass.data.get("area_registry")
                if area_registry and resolved_area_id and resolved_area_id in area_registry.areas:
                    entry["area"] = area_registry.areas[resolved_area_id]
                else:
                    entry["area"] = None
            elif prop == "device_class":
                state = hass.states.get(entry.get("entity_id"))
                if state:
                    entry["device_class"] = state.attributes.get("device_class")
            # ...future property injections...
    return entries

def gather_candidate_entities(hass, entity_name_or_id=None, domain=None, device_classes=None, area_ids=None):
    _LOGGER.debug("Gathering candidate entities with filters: entity_id=%s, domain=%s, device_classes=%s, area_ids=%s", entity_name_or_id, domain, device_classes, area_ids)
    _LOGGER.debug("Gathering version:  v1.0.1")
    candidate_entities = []
    entity_registry = hass.data.get("entity_registry")
    device_reg = hass.data.get("device_registry")
    if entity_registry:
        total_entities = 0
        filtered_by_expose = 0
        filtered_by_entity_id = 0
        filtered_by_domain = 0
        filtered_by_device_class = 0
        filtered_by_area = 0

        for ent in entity_registry.entities.values():
            total_entities += 1
            expose_option = ent.options.get("conversation", {}).get("should_expose", False)
            if not expose_option:
                filtered_by_expose += 1
                continue
            state_obj = hass.states.get(ent.entity_id)
            if not state_obj:
                continue
            #skip sensor.date_time entity
            if ent.entity_id == "sensor.date_time":
                continue
            if entity_name_or_id:
                norm_input = normalize_text(entity_name_or_id)
                friendly = normalize_text(state_obj.attributes.get("friendly_name", ""))
                actual = normalize_text(state_obj.entity_id)
                aliases = ent.options.get("aliases", [])
                norm_aliases = [normalize_text(a) for a in aliases]
                if friendly != norm_input and actual != norm_input and norm_input not in norm_aliases:
                    filtered_by_entity_id += 1
                    #_LOGGER.debug("Filtered by entity_norm_input: %s, friendly=%s, actual=%s, aliases=%s", norm_input, friendly, actual, norm_aliases)  
                                  
                    continue
            # Domain filtering
            if domain:
                if isinstance(domain, str):
                    domain = [domain]
                if len(domain) > 0 and not any(ent.entity_id.startswith(f"{d}.") for d in domain):
                    filtered_by_domain += 1
                    #_LOGGER.debug("Filtered by domain: %s", ent.entity_id)
                    continue
            ### Device class filtering


            if device_classes:
                #preload device_class from state object
                device_class_attr = state_obj.attributes.get("device_class", None)
                if isinstance(device_class_attr, str):
                    device_class_attr = [device_class_attr]  # Convert single string to list
                elif not isinstance(device_class_attr, list):
                    device_class_attr = []  # Default to empty list if not a string or list
                
                # convert device_classes to list if it's a string
                if isinstance(device_classes, str):
                    device_classes = [device_classes]             

                if len(device_classes) > 0 and not any(dc in device_classes for dc in device_class_attr):
                    filtered_by_device_class += 1
                    _LOGGER.debug("Filtered by device_class: %s", device_class_attr)
                    continue    

            ent_area_id = ent.area_id
            if not ent_area_id and device_reg and ent.device_id in device_reg.devices:
                ent_area_id = device_reg.devices[ent.device_id].area_id

            # Skip entities without an area if area filtering is applied
            if area_ids and not ent_area_id:
                filtered_by_area += 1
                continue

            if area_ids and not any(ent_area_id == aid for aid in area_ids):
                filtered_by_area += 1
                continue

            # Log passed criteria before appending the entity, but only for the first 20 candidates

            passed_criteria = []
            if entity_name_or_id:
                passed_criteria.append(f"entity_id={entity_name_or_id}")
            if domain:
                passed_criteria.append(f"domain={domain}")
            if device_classes:
                passed_criteria.append(f"device_classes={device_classes}")
            if area_ids:
                passed_criteria.append(f"area_ids={area_ids}")
            if expose_option:
                passed_criteria.append("exposed=True")
            if state_obj.state:
                passed_criteria.append(f"state={state_obj.state}")

            _LOGGER.debug(
                "Entity %s passed criteria: %s", 
                ent.entity_id, 
                ", ".join(passed_criteria)
            )

            candidate_entities.append(state_obj)

        _LOGGER.debug("Total entities: %d", total_entities)
        _LOGGER.debug("Filtered by expose: %d", filtered_by_expose)
        _LOGGER.debug("Filtered by entity_id: %d", filtered_by_entity_id)
        _LOGGER.debug("Filtered by domain: %d", filtered_by_domain)
        _LOGGER.debug("Filtered by device_class: %d", filtered_by_device_class)
        _LOGGER.debug("Filtered by area: %d", filtered_by_area)

    return list({s.entity_id: s for s in candidate_entities}.values())

# --- High-Level Query Runner ---
async def get_raw_entries(hass, url, headers, params, candidate_entities, end_str, max_iter):
    # If the number of candidates is less than max_iter, fetch using each candidate's entity_id separately
    if candidate_entities and len(candidate_entities) < max_iter:
        raw_entries = []
        for state_obj in candidate_entities:
            params_local = {"end_time": end_str, "entity_id": state_obj.entity_id}
            entries = await fetch_logbook_data(hass, url, headers, params_local)
            raw_entries.extend(entries)
    else:
        if candidate_entities and len(candidate_entities) == 1:
            params["entity_id"] = candidate_entities[0].entity_id
        raw_entries = await fetch_logbook_data(hass, url, headers, params)
    # Sort raw_entries by the "when" field to ensure proper time order
    try:
        raw_entries.sort(key=lambda entry: datetime.fromisoformat(entry.get("when", "").replace("Z", "+00:00")))
    except Exception as e:
        _LOGGER.warning("Failed to sort raw_entries: %s", e)
    return raw_entries

async def run_log_query(
    hass,
    ha_token,
    question,
    question_type,
    area_name_or_alias=None,
    time_period=None,
    entity_name_or_alias=None,
    domain=None,
    device_classes=None,
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

    area_mappings = fetch_area_mappings(hass)

    area_ids = resolve_area_ids(area_mappings, area_name_or_alias)
    #device_class_map, _ = fetch_entity_mappings(hass)

    # Új megközelítés: candidate list feltöltése teljes state objektummal, nem csak entity_id-val
    max_iter = 5
    candidate_entities = gather_candidate_entities(hass, entity_name_or_alias, domain, device_classes, area_ids)
    # Deduplicate candidate state objects by entity_id
    candidate_entities = list({s.entity_id: s for s in candidate_entities}.values())
    # Extra debug logging: if extra filters applied, log detailed candidate entity_ids;
    # otherwise, log only the total count.
    if entity_name_or_alias or domain or device_classes or area_ids:
        _LOGGER.debug("Detailed candidate entities: %s", [s.entity_id for s in candidate_entities])
    else:
        _LOGGER.info("Candidate entities count (only expose filter applied): %d", len(candidate_entities))
    
    #no candidate entities found
    if not candidate_entities:
        _LOGGER.warning("No candidate entities found for the given filters.")
        return "No entities found for the given filters."

    url = f"{hass.config.internal_url or hass.config.external_url}/api/logbook/{start_str}"
    headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"}
    params = {"end_time": end_str}
    
    # Call the new helper function to get and sort raw entries
    raw_entries = await get_raw_entries(hass, url, headers, params, candidate_entities, params["end_time"], max_iter)
    
    # Step 4: Filter entries using candidate_entities (matching via state_obj.entity_id)
    filtered = filter_logbook_entries(raw_entries, candidate_entities, state=state)
    
    # Step 5: Inject resolved properties into each filtered entry via the generic helper function
    inject_resolved_properties(hass, filtered, ["area","device_class"])
    
    # Step 6: Format final output
    return format_logbook_entries(filtered, char_limit)

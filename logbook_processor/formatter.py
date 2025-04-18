def format_events(events):
    formatted_events = []
    grouped_by_time = {}

    for event in events:
        timestamp = event.get("timestamp")
        entity_id = event.get("entity_id")
        state = event.get("state")
        event_type = entity_id.split(".")[0] if entity_id else "unknown"
        device_class = event.get("device_class", "")
        domain = entity_id.split(".")[1] if entity_id else "unknown"

        # Add context as event_description based on device_class
        event_description = ""
        if device_class == "occupancy":
            if state == "on":
                event_description = "motion detected"
            elif state == "off":
                event_description = "motion stopped"
        elif device_class == "door":
            if state == "on":
                event_description = "door opened"
            elif state == "off":
                event_description = "door closed"
        elif device_class == "window":
            if state == "on":
                event_description = "window opened"
            elif state == "off":
                event_description = "window closed"
        elif device_class == "presence":
            if state == "on" or state == "home":
                event_description = "presence detected"
            elif state == "off" or state == "not_home":
                event_description = "presence stopped"
        elif domain == "light":
            if state == "on":
                event_description = "light turned on"
            elif state == "off":
                event_description = "light turned off"
        elif domain == "switch":
            if state == "on":
                event_description = "switch turned on"
            elif state == "off":
                event_description = "switch turned off"
        elif domain == "climate":
            if state == "heat":
                event_description = "heating activated"
            elif state == "cool":
                event_description = "cooling activated"
            elif state == "off":
                event_description = "climate system turned off"
        elif domain == "sensor":
            if state == "on":
                event_description = "sensor activated"
            elif state == "off":
                event_description = "sensor deactivated"
        elif domain == "alarm_control_panel":
            if state == "armed_away":
                event_description = "alarm armed away"
            elif state == "armed_home":
                event_description = "alarm armed home"
            elif state == "disarmed":
                event_description = "alarm disarmed"
        elif domain == "media_player":
            if state == "playing":
                event_description = "media playing"
            elif state == "paused":
                event_description = "media paused"
            elif state == "stopped":
                event_description = "media stopped" 
        elif domain == "vacuum":
            if state == "cleaning":
                event_description = "vacuum cleaning"
            elif state == "docked":
                event_description = "vacuum docked"
            elif state == "idle":
                event_description = "vacuum idle"
        elif domain == "fan":
            if state == "on":
                event_description = "fan turned on"
            elif state == "off":
                event_description = "fan turned off"
        elif domain == "water_heater":
            if state == "on":
                event_description = "water heater on"
            elif state == "off":
                event_description = "water heater off"
                
        # Format the entry line based on whether we have an event description or not
        entry_text = f"{entity_id} {state}"
        if event_description:
            entry_text = f"{entity_id} {state} ({event_description})"

        # Group events by timestamp
        if timestamp not in grouped_by_time:
            grouped_by_time[timestamp] = []
        grouped_by_time[timestamp].append(entry_text)

    # Format grouped events
    for timestamp, entries in grouped_by_time.items():
        formatted_events.append(f"{timestamp}:")
        for entry in entries:
            formatted_events.append(f"  - {entry}")

    return "\n".join(formatted_events)

# Example usage
# events = [
#     {"timestamp": "2025-04-13 15:30:57", "entity_id": "binary_sensor.etkezo_mozgaserzekelo_occupancy_2", "state": "off"},
#     {"timestamp": "2025-04-13 15:30:57", "entity_id": "binary_sensor.konyha_mozgaserzekelo_occupancy", "state": "off"},
#     {"timestamp": "2025-04-13 15:30:38", "entity_id": "binary_sensor.etkezo_mozgaserzekelo_occupancy_2", "state": "on"},
# ]
# print(format_events(events))
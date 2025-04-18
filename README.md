# Logbook Expose Integration

## Overview
The **Logbook Expose** integration for Home Assistant provides seamless access to logbook events for conversation agents such as Google AI, ChatGPT, and others. This integration enables querying and analyzing logbook data with extended attributes, offering a flexible way to retrieve and process log information based on specific parameters like time periods, areas, entities, and more. By bridging Home Assistant's logbook with conversational AI, it empowers users to interact with their smart home data in a natural and intuitive way.

## Features
- Query logbook events using custom time periods (e.g., `today`, `last_3_hours`, `last_5_minutes`).
- Filter events by area, entity, domain, device class, or state.
- Supports dynamic configuration through the Home Assistant UI.
- Provides detailed responses for automation and intent scripts.
- Automatically sets up intent scripts for natural language queries.

## Installation
1. Clone the repository into your Home Assistant `custom_components` directory:
   ```bash
   git clone https://github.com/lopeti/logbook_expose.git custom_components/logbook_expose
   ```
2. Restart Home Assistant.
3. Navigate to **Settings > Devices & Services > Add Integration** and search for "Logbook Expose".

## Configuration
### Configuration via UI
1. Add the integration through the Home Assistant UI.
2. Provide the required `ha_token` during setup.
3. Optionally enable file logging for debugging purposes.
4. Configure the character limit for response text.

### Configuration Options
- **ha_token**: The Home Assistant token for API access.
- **enable_file_logging**: Enable or disable file logging for debugging.
- **char_limit**: Maximum number of characters allowed in the response text (default: 262,144).

## Usage
### Service: `logbook_expose.log_query`
This service allows querying the logbook with specific parameters.

#### Parameters:
- `question` (string): The text of the question.
- `question_type` (string): The type of the question (e.g., `custom_query`).
- `area_id` (string): The affected area. It can be the area name or alias. Supports comma-separated values for multiple areas (e.g., `kitchen, dining room, hallway`).
- `time_period` (string): The time period (e.g., `today`, `last 3 hours`, `last 5 minutes`).
- `entity_id` (string): The ID of the affected entity.
- `domain` (string): The affected domain (e.g., `light`, `sensor`).
- `device_class` (string): The type of the device.
- `state` (string): The state of the entity.
- `start_time` (string, optional): Explicit start time for the query (format: `YYYY-MM-DD HH:MM:SS`). Optional if `time_period` is filled.
- `end_time` (string, optional): Explicit end time for the query (format: `YYYY-MM-DD HH:MM:SS`). Optional if `time_period` is filled.

#### Response Format:
The response is formatted as a CSV-like text with three columns:
```
Time, Entity, Event
2025-04-13 20:14:07, Kitchen Light, turned on
2025-04-13 20:15:32, Front Door, door opened
```

Events are displayed with:
- Timestamps in local time
- Friendly entity names instead of entity_ids
- Human-readable event descriptions based on device_class and state

#### Example Service Call:
```yaml
service: logbook_expose.log_query
data:
  question: "What happened in the kitchen?"
  question_type: "area_events_now"
  area_id: "kitchen"
  time_period: "last_3_hours"
  entity_id: ""
  domain: ""
  device_class: ""
  state: ""
```

### Intent Integration
The integration supports natural language queries through the `LBEQueryLogbook` intent. This allows users to ask questions like "What happened in the kitchen in the last hour?" or "What happened with the living room light today?"

#### Intent Slots
- `question` (string): The text of the question.
- `area` (string): The area to query (e.g., "kitchen").
- `time_period` (string): The time period to query (e.g., "last hour").
- `entity_id` (string): The specific entity to query.
- `domain` (string): The domain of the entity (e.g., "light").
- `device_class` (string): The device class of the entity (e.g., "motion").
- `state` (string): The state of the entity (e.g., "on").

#### Example Queries:
- "What happened in the living room in the last hour?"
- "What happened with the kitchen light today?"
- "What happened in the last 5 minutes?"
- "What happened between 2024-01-01 00:00:00 and 2024-01-02 00:00:00?"

## Debugging
Enable file logging during setup to log requests and responses for debugging purposes. Logs are stored in the `log` directory within the integration folder.

## Contributing
Contributions are welcome! Please submit a pull request or open an issue on the [GitHub repository](https://github.com/lopeti/logbook_expose).

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

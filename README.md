# Logbook Expose Integration

## Overview
The **Logbook Expose** integration for Home Assistant is designed to provide seamless access to logbook events for conversation agents such as Google AI, ChatGPT, and others. This integration enables querying and analyzing logbook data with extended attributes, offering a flexible way to retrieve and process log information based on specific parameters like time periods, areas, entities, and more. By bridging Home Assistant's logbook with conversational AI, it empowers users to interact with their smart home data in a natural and intuitive way.

## Features
- Query logbook events using custom time periods (e.g., `today`, `last_3_hours`, `last_5_minutes`).
- Filter events by area, entity, domain, device class, or state.
- Supports dynamic configuration through the Home Assistant UI.
- Provides detailed responses for automation and intent scripts.

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
- **skip_unknown_states**: Skip entities with unknown state values (default: true).

## Usage
### Service: `logbook_expose.log_query`
This service allows querying the logbook with specific parameters.

#### Parameters:
- `question` (string): The text of the question.
- `question_type` (string): The type of the question (e.g., `happenings`, `area_events_now`).
- `area_id` (string): The affected area name (e.g., `kitchen`, `living room`). Supports comma-separated values for multiple areas (e.g., `kitchen, dining room, hallway`).
- `time_period` (string): The time period (e.g., `today`, `last_3_hours`, `last_5_minutes`).
- `entity_id` (string): The ID of the affected entity.
- `domain` (string): The affected domain (e.g., `light`, `sensor`).
- `device_class` (string): The type of the device.
- `state` (string): The state of the entity.

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

### Intent Scripts
The integration supports intent scripts for natural language queries. Example intents include:
- **LogAllEventsNow**: Query all events for the current time.
- **LogAreaEventsNow**: Query events for a specific area and time period.

#### Example Intent Script:
```yaml
LogAreaEventsNow:
  action:
    - variables:
        area: "{{ area }}"
        time_period: "{{ time_period | default('now') }}"
        query: "What happened in the {{ area }} area {{ time_period }}"
        question_type: "area_events_now"
        area_id: "{{ area }}"
    - service: logbook_expose.log_query
      data:
        question: "{{ query }}"
        question_type: "{{ question_type }}"
        area_id: "{{ area_id }}"
        time_period: "{{ time_period }}"
        entity_id: ""
        domain: ""
        device_class: ""
        state: ""
  speech:
    text: "The log query result: {{ state_attr('logbook_expose.last_result', 'logbook') if state_attr('logbook_expose.last_result', 'logbook') else 'no events found.' }}"
```

## Supported Time Periods
The following time periods are supported:
- `today`
- `yesterday`
- `last_hour`
- `last_3_hours`
- `last_5_hours`
- `last_8_hours`
- `last_12_hours`
- `last_24h`
- `last_1_minutes`
- `last_5_minutes`
- `last_10_minutes`
- `last_15_minutes`
- `last_30_minutes`

## Custom Scripts Directory
To use custom intent scripts with the Logbook Expose integration, you need to create a directory named `custom_scripts` in your Home Assistant configuration folder. This folder will store any additional or user-defined intent scripts.

Example path:
```
/config/custom_scripts
```

## Built-in Intent Script Copying
The integration automatically copies the built-in intent script file `logbook_expose_intent_scripts.yaml` to the `intent_scripts` directory in your Home Assistant configuration folder. This ensures that the default intents are always available for use.

The copied file can be found at:
```
/config/intent_scripts/logbook_expose_intent_scripts.yaml
```
If the file does not exist in the source directory, a warning will be logged.

## Including Intent Scripts in Configuration
To include the intent scripts in your Home Assistant configuration, add the following to your `configuration.yaml` file:

```yaml
intent_script: !include_dir_merge_named intent_scripts
```

This configuration will merge all YAML files in the `intent_scripts` directory and make them available as intent scripts in Home Assistant.

## Debugging
Enable file logging during setup to log requests and responses for debugging purposes. Logs are stored in the `log` directory within the integration folder.

## Contributing
Contributions are welcome! Please submit a pull request or open an issue on the [GitHub repository](https://github.com/lopeti/logbook_expose).

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
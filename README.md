# Logbook Expose Integration

**Note:** This project is in an early stage of development.

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

### Intent Scripts
The integration supports intent scripts for natural language queries. Example intents include:
- **LBEQueryLogbook**: Query events using a flexible time period, device, and area.

#### Example Intent Script:
```yaml
LBEQueryLogbook:
  description: |
    Queries the Home Assistant logbook and returns events based on specified criteria.
    This intent allows users to ask questions about events related to devices, areas, or general activity within a specified time period.
    The response provides a summary of the log events, including timestamps, entities, and event descriptions.

    Example questions:
      - "What happened in the living room in the last hour?"
      - "What happened with the kitchen light today?"
      - "What happened in the last 5 minutes?"
      - "What happened between 2024-01-01 00:00:00 and 2024-01-02 00:00:00?"
      - "Tell me about the events in the last 3 hours."
      - "What happened with the thermostat yesterday?"
      - "What happened in the bedroom 2 days ago?"
      - "How many times did the doorbell ring in the last hour?"
      - "Since when has the entrance door been open?"
      - "What is the total duration of the terrace door being open in the last hour?"
      - "List all the bath usage events in the last 3 hours with timestamps and durations."
      You can use multiple calls to the logbook_expose.log_query service to comparing different time periods or devices.
      - "Did you see more animals in the garden tonight or last night?

    Parameters:
      - time_period: The time period to query (e.g., last 1 hour, today, yesterday, last 5 minutes, last 3 hours, 2 days ago). Defaults to last_hour if not provided.
      - device: The name of the device to filter events by.
      - area: The name of the area to filter events by.
      - start_time: Explicit start time for the query (format: YYYY-MM-DD HH:MM:SS). Optional.
      - end_time: Explicit end time for the query (format: YYYY-MM-DD HH:MM:SS). Optional.

    Response:
      Returns a plain text summary of log events matching the specified criteria.
      Sample response:
        "The log query result:\n- 2024-01-01 12:00:00: Living room light turned on\n- 2024-01-01 12:05:00: Living room light turned off"
      If no events are found, returns a message indicating that no events were found.
      You can use the `logbook_expose.last_result` entity to access the raw logbook data for further processing or display.      
  action:
    - variables:
        time_period: "{{ time_period | default('last 1 hour') }}"
        device: "{{ device | default('') }}"
        area: "{{ area | default('') }}"
        start_time: "{{ start_time | default('') }}"
        end_time: "{{ end_time | default('') }}"
        query: >
          {% if start_time and end_time %}
            What happened between {{ start_time }} and {{ end_time }}?
          {% elif device and area %}
            What happened with the {{ device }} device in the {{ area }} area in the {{ time_period }}?
          {% elif device %}
            What happened with the {{ device }} device in the {{ time_period }}?
          {% elif area %}
            What happened in the {{ area }} area in the {{ time_period }}?
          {% else %}
            What happened in the {{ time_period }}?
          {% endif %}
        question_type: "custom_query"
    - service: logbook_expose.log_query
      data:
        question: "{{ query }}"
        question_type: "{{ question_type }}"
        time_period: "{{ time_period }}"
        area: "{{ area }}"
        entity: "{{ device }}"
        domain: ""
        device_class: ""
        state: ""
        start_time: "{{ start_time }}"
        end_time: "{{ end_time }}"
  speech:
    text: "The log query result:\n{{ state_attr('logbook_expose.last_result', 'logbook') if state_attr('logbook_expose.last_result', 'logbook') else 'no events found.' }}"

### AI Agent Prompt
To use the `LBEQueryLogbook` intent effectively, include the following parameters in the AI agent prompt:

#### LBEQueryLogbook Parameters:
- **time_period**: The time period to query (e.g., `last 1 hour`, `today`, `yesterday`, `last 5 minutes`, `last 3 hours`, `2 days ago`). Optional if `start_time` and `end_time` are filled.
- **device**: The name of the device to filter events by.
- **area**: The name of the area to filter events by.
- **start_time**: Explicit start time for the query (format: `YYYY-MM-DD HH:MM:SS`). Optional if `time_period` is filled.
- **end_time**: Explicit end time for the query (format: `YYYY-MM-DD HH:MM:SS`). Optional if `time_period` is filled.

## Supported Time Periods
The following time periods are supported:
- `today`
- `yesterday`
- `last 1 hour` (default)
- any time period like `last x minutes`, `last x hours`, `x days ago`

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
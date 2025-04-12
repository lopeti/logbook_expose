import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

class LogbookExposeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Logbook Expose."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            ha_token = user_input.get("ha_token", "").strip()
            if not ha_token:
                errors["ha_token"] = "Token cannot be empty."
            else:
                return self.async_create_entry(title="Logbook Expose", data=user_input)

        data_schema = vol.Schema({
            vol.Optional("ha_token", default=""): str,
            vol.Optional("enable_file_logging", default=False): bool,
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return LogbookExposeOptionsFlowHandler(config_entry)

class LogbookExposeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Logbook Expose."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            ha_token = user_input.get("ha_token", "").strip()
            if not ha_token:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._get_options_schema(),
                    errors={"ha_token": "Token cannot be empty."}
                )
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init", data_schema=self._get_options_schema()
        )

    def _get_options_schema(self):
        return vol.Schema({
            vol.Optional("ha_token", default=self.config_entry.options.get("ha_token", "")): str,
            vol.Optional("enable_file_logging", default=self.config_entry.options.get("enable_file_logging", False)): bool,
        })
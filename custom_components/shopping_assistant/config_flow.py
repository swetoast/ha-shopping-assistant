"""Config flow for Shopping Assistant."""
from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_AUTO_ADD_TO_SHOPPING_LIST,
    CONF_CONTACT_EMAIL,
    CONF_ENABLE_OFF_SUBMISSION,
    CONF_ENABLE_WEBHOOK,
    CONF_LANGUAGE_PRIORITY,
    CONF_OFF_PASSWORD,
    CONF_OFF_TEST_MODE,
    CONF_OFF_USERNAME,
    CONF_SHOPPING_LIST_ENTITY,
    CONF_SHOW_NOTIFICATIONS,
    CONF_TRACK_EXPIRY,
    CONF_TRACK_PRICES,
    CONF_WEBHOOK_LOCAL_ONLY,
    DATA_APP_UUID,
    DATA_WEBHOOK_ID,
    DEFAULT_OPTIONS,
    DOMAIN,
    LEGACY_DOMAIN,
)
from .scanner_webhook import webhook_url

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_LANGUAGE_RE = re.compile(r"^[a-z]{2}$")

_TEXT = TextSelector()
_EMAIL = TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL))
_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
_BOOL = BooleanSelector()
_TODO = EntitySelector(EntitySelectorConfig(domain="todo"))

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONTACT_EMAIL): _EMAIL,
        vol.Required(CONF_SHOPPING_LIST_ENTITY): _TODO,
        vol.Required(CONF_AUTO_ADD_TO_SHOPPING_LIST): _BOOL,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONTACT_EMAIL): _EMAIL,
        vol.Required(CONF_LANGUAGE_PRIORITY): _TEXT,
        vol.Required(CONF_SHOPPING_LIST_ENTITY): _TODO,
        vol.Required(CONF_AUTO_ADD_TO_SHOPPING_LIST): _BOOL,
        vol.Required(CONF_SHOW_NOTIFICATIONS): _BOOL,
        vol.Required(CONF_TRACK_PRICES): _BOOL,
        vol.Required(CONF_TRACK_EXPIRY): _BOOL,
        vol.Required(CONF_ENABLE_WEBHOOK): _BOOL,
        vol.Required(CONF_WEBHOOK_LOCAL_ONLY): _BOOL,
        vol.Required(CONF_ENABLE_OFF_SUBMISSION): _BOOL,
        vol.Optional(CONF_OFF_USERNAME): _TEXT,
        vol.Optional(CONF_OFF_PASSWORD): _PASSWORD,
        vol.Required(CONF_OFF_TEST_MODE): _BOOL,
    }
)


def _valid_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value)) and not value.endswith("@example.com")


class ShoppingAssistantConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up Shopping Assistant."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the contact email and shopping list."""
        errors: dict[str, str] = {}
        defaults = {**DEFAULT_OPTIONS, **self._legacy_options()}
        if user_input is not None:
            email = user_input[CONF_CONTACT_EMAIL].strip()
            if _valid_email(email):
                return self.async_create_entry(
                    title="Shopping Assistant",
                    data={DATA_APP_UUID: uuid4().hex},
                    options={**defaults, **user_input, CONF_CONTACT_EMAIL: email},
                )
            errors[CONF_CONTACT_EMAIL] = "invalid_email"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, user_input or defaults
            ),
            errors=errors,
        )

    def _legacy_options(self) -> dict[str, Any]:
        """Return the options of an EAN Reader entry, if one exists."""
        if not (legacy := self.hass.config_entries.async_entries(LEGACY_DOMAIN)):
            return {}
        options = {k: v for k, v in legacy[0].options.items() if k in DEFAULT_OPTIONS}
        if isinstance(languages := options.get(CONF_LANGUAGE_PRIORITY), str):
            options[CONF_LANGUAGE_PRIORITY] = [
                part.strip().lower() for part in languages.split(",") if part.strip()
            ]
        return options

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ShoppingAssistantOptionsFlow:
        """Return the options flow."""
        return ShoppingAssistantOptionsFlow()


class ShoppingAssistantOptionsFlow(OptionsFlowWithReload):
    """Change Shopping Assistant options; the entry reloads after saving."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show all options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            options = {**DEFAULT_OPTIONS, **user_input}
            options[CONF_CONTACT_EMAIL] = options[CONF_CONTACT_EMAIL].strip()
            languages = [
                part.strip().lower()
                for part in str(options[CONF_LANGUAGE_PRIORITY]).split(",")
                if part.strip()
            ]
            if not _valid_email(options[CONF_CONTACT_EMAIL]):
                errors[CONF_CONTACT_EMAIL] = "invalid_email"
            if not languages or not all(_LANGUAGE_RE.match(lang) for lang in languages):
                errors[CONF_LANGUAGE_PRIORITY] = "invalid_language"
            if options[CONF_ENABLE_OFF_SUBMISSION] and not (
                options[CONF_OFF_USERNAME] and options[CONF_OFF_PASSWORD]
            ):
                errors["base"] = "credentials_required"
            if not errors:
                options[CONF_LANGUAGE_PRIORITY] = languages
                return self.async_create_entry(data=options)

        current = {**DEFAULT_OPTIONS, **self.config_entry.options}
        if not isinstance(languages := current[CONF_LANGUAGE_PRIORITY], str):
            current[CONF_LANGUAGE_PRIORITY] = ", ".join(languages)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, user_input or current
            ),
            errors=errors,
            description_placeholders={"webhook_url": self._webhook_url()},
        )

    def _webhook_url(self) -> str:
        """Return the webhook URL, or a hint when the webhook is off."""
        if webhook_id := self.config_entry.data.get(DATA_WEBHOOK_ID):
            return webhook_url(self.hass, webhook_id)
        return "not created yet (enable the webhook and save)"

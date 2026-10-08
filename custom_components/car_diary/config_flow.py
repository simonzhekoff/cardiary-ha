"""Config flow for Car Diary."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CarDiaryAuthError, CarDiaryClient, CarDiaryError
from .const import CONF_TOKEN, CONF_USER_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class CarDiaryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Log in once; only the token is kept."""

    VERSION = 1

    async def _login(self, user_input: dict[str, Any], errors: dict[str, str]):
        client = CarDiaryClient(async_get_clientsession(self.hass))
        try:
            return await client.login(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
        except CarDiaryAuthError:
            errors["base"] = "invalid_auth"
        except CarDiaryError as err:
            _LOGGER.error("Car Diary login failed: %s", err)
            errors["base"] = "cannot_connect"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user = await self._login(user_input, errors)
            if user is not None:
                await self.async_set_unique_id(str(user["id"]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_TOKEN: user["api_token"],
                        CONF_USER_ID: user["id"],
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            user = await self._login(
                {CONF_EMAIL: entry.data[CONF_EMAIL], **user_input}, errors
            )
            if user is not None:
                await self.async_set_unique_id(str(user["id"]))
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_TOKEN: user["api_token"]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )

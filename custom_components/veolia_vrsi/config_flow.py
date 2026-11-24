"""Config flow pentru Veolia VRSI."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .api import (
    VeoliaAuthError,
    VeoliaBlockedError,
    VeoliaBridgeAuthError,
    VeoliaBridgeClient,
    VeoliaError,
)
from .const import (
    CONF_BRIDGE_TOKEN,
    CONF_BRIDGE_URL,
    CONF_LOCATIONS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
    MAX_SCAN_INTERVAL_HOURS,
    MIN_SCAN_INTERVAL_HOURS,
)
from .parser import LocationData, build_locations

_LOGGER = logging.getLogger(__name__)

CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
        ),
    }
)

BRIDGE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BRIDGE_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Required(CONF_BRIDGE_TOKEN): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


def _interval_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=MIN_SCAN_INTERVAL_HOURS,
            max=MAX_SCAN_INTERVAL_HOURS,
            step=1,
            unit_of_measurement="h",
            mode=NumberSelectorMode.SLIDER,
        )
    )


def _locations_selector(locations: dict[str, LocationData]) -> SelectSelector:
    options = [
        SelectOptionDict(value=code, label=f"{loc.address} ({code})")
        for code, loc in locations.items()
    ]
    return SelectSelector(
        SelectSelectorConfig(options=options, multiple=True, mode=SelectSelectorMode.LIST)
    )


def _error_key(err: Exception) -> str:
    if isinstance(err, VeoliaAuthError):
        return "invalid_auth"
    if isinstance(err, VeoliaBlockedError):
        return "waf_blocked"
    if isinstance(err, VeoliaBridgeAuthError):
        return "bridge_auth"
    if isinstance(err, VeoliaError):
        return "cannot_connect"
    return "unknown"


class VeoliaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Adăugarea unui cont Veolia VRSI."""

    VERSION = 1

    def __init__(self) -> None:
        self._bridge_url: str = ""
        self._bridge_token: str = ""
        self._email: str = ""
        self._password: str = ""
        self._locations: dict[str, LocationData] = {}

    # ------------------------------------------------------------ bridge
    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> ConfigFlowResult:
        """Add-on-ul Veolia Bridge s-a anunțat prin Supervisor."""
        config = discovery_info.config
        self._bridge_url = f"http://{config['host']}:{config['port']}"
        self._bridge_token = str(config["token"])

        for entry in self._async_current_entries(include_ignore=False):
            if (
                entry.data.get(CONF_BRIDGE_URL) != self._bridge_url
                or entry.data.get(CONF_BRIDGE_TOKEN) != self._bridge_token
            ):
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_BRIDGE_URL: self._bridge_url,
                        CONF_BRIDGE_TOKEN: self._bridge_token,
                    },
                )
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
        if self._async_current_entries(include_ignore=False):
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(f"hassio_{discovery_info.uuid}")
        self._abort_if_unique_id_configured()
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return await self.async_step_credentials()
        return self.async_show_form(step_id="hassio_confirm")

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configurare manuală: URL-ul și token-ul bridge-ului."""
        if user_input is not None:
            self._bridge_url = user_input[CONF_BRIDGE_URL].strip().rstrip("/")
            self._bridge_token = user_input[CONF_BRIDGE_TOKEN].strip()
            return await self.async_step_credentials()
        return self.async_show_form(step_id="user", data_schema=BRIDGE_SCHEMA)

    # ------------------------------------------------------------ cont
    async def _validate(self, email: str, password: str) -> dict[str, LocationData]:
        client = VeoliaBridgeClient(
            async_get_clientsession(self.hass),
            self._bridge_url,
            self._bridge_token,
            email,
            password,
        )
        return build_locations(await client.get_snapshot())

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._email = user_input[CONF_EMAIL].strip()
            self._password = user_input[CONF_PASSWORD]
            await self.async_set_unique_id(self._email.lower(), raise_on_progress=False)
            self._abort_if_unique_id_configured()
            try:
                self._locations = await self._validate(self._email, self._password)
            except Exception as err:  # noqa: BLE001
                errors["base"] = _error_key(err)
                if errors["base"] == "unknown":
                    _LOGGER.exception("Eroare neașteptată")
                else:
                    _LOGGER.debug("Validare eșuată: %s", err)
            else:
                if not self._locations:
                    errors["base"] = "no_locations"
                else:
                    return await self.async_step_locations()

        return self.async_show_form(
            step_id="credentials",
            data_schema=self.add_suggested_values_to_schema(
                CREDENTIALS_SCHEMA, {CONF_EMAIL: self._email}
            ),
            errors=errors,
        )

    async def async_step_locations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        codes = list(self._locations)
        if user_input is not None or len(codes) == 1:
            selected = (user_input or {}).get(CONF_LOCATIONS) or codes
            return self.async_create_entry(
                title=self._email,
                data={
                    CONF_EMAIL: self._email,
                    CONF_PASSWORD: self._password,
                    CONF_BRIDGE_URL: self._bridge_url,
                    CONF_BRIDGE_TOKEN: self._bridge_token,
                },
                options={
                    CONF_LOCATIONS: selected,
                    CONF_SCAN_INTERVAL: (user_input or {}).get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS
                    ),
                },
            )
        return self.async_show_form(
            step_id="locations",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCATIONS, default=codes): _locations_selector(
                        self._locations
                    ),
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_HOURS
                    ): _interval_selector(),
                }
            ),
        )

    # ------------------------------------------------------------ reauth
    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        self._email = entry_data[CONF_EMAIL]
        self._bridge_url = entry_data[CONF_BRIDGE_URL]
        self._bridge_token = entry_data[CONF_BRIDGE_TOKEN]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._validate(self._email, user_input[CONF_PASSWORD])
            except Exception as err:  # noqa: BLE001
                errors["base"] = _error_key(err)
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            description_placeholders={"email": self._email},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return VeoliaOptionsFlow()


class VeoliaOptionsFlow(OptionsFlow):
    """Reconfigurare: locuri de consum și interval de actualizare."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={**self.config_entry.options, **user_input})

        coordinator = getattr(self.config_entry, "runtime_data", None)
        locations = build_locations(coordinator.raw) if coordinator and coordinator.raw else {}
        current = self.config_entry.options.get(CONF_LOCATIONS) or list(locations)
        schema: dict[Any, Any] = {}
        if locations:
            schema[vol.Required(CONF_LOCATIONS, default=current)] = _locations_selector(locations)
        schema[
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS
                ),
            )
        ] = _interval_selector()
        return self.async_show_form(step_id="init", data_schema=vol.Schema(schema))

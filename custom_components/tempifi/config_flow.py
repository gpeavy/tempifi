"""Config flow for tempi.fi BLE Tracker integration."""
from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TempiFiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for tempi.fi BLE Tracker."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle a flow initialized by Bluetooth discovery."""
        address = discovery_info.address.upper()
        _LOGGER.debug("Discovered tempi.fi device via BLE: %s", address)
        
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": f"tempi.fi {address}"}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm setup of a discovered device."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.context["title_placeholders"]["name"],
                data={},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self.context["title_placeholders"]["name"]
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user (manual configuration)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input["address"].upper().strip()
            # Simple validation check on MAC address format (must be 12 hex digits with or without colons)
            clean_addr = address.replace(":", "")
            if len(clean_addr) == 12 and all(c in "0123456789ABCDEF" for c in clean_addr):
                # Standardize with colons
                formatted_addr = ":".join(clean_addr[i:i+2] for i in range(0, 12, 2))
                await self.async_set_unique_id(formatted_addr)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"tempi.fi {formatted_addr}",
                    data={},
                )
            errors["base"] = "invalid_mac"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("address"): str,
            }),
            errors=errors,
        )

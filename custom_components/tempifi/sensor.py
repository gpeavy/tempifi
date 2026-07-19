"""Sensor platform for tempi.fi BLE Tracker integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    address = entry.unique_id.upper()
    async_add_entities([
        TempiFiSensor(entry.entry_id, "temperature", address),
        TempiFiSensor(entry.entry_id, "humidity", address),
    ])


class TempiFiSensor(SensorEntity):
    """Representation of a tempi.fi Sensor."""

    _attr_has_entity_name = True

    def __init__(self, entry_id: str, sensor_type: str, address: str) -> None:
        """Initialize the sensor."""
        self._entry_id = entry_id
        self._sensor_type = sensor_type
        self._address = address
        self._attr_unique_id = f"{address}_{sensor_type}"

        if sensor_type == "temperature":
            self._attr_name = "Temperature"
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_state_class = SensorStateClass.MEASUREMENT
        else:
            self._attr_name = "Humidity"
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT

        # Link this entity to the Device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=f"tempi.fi {address}",
            manufacturer="tempi.fi",
            model="BLE Temperature & Humidity Sensor",
        )

    async def async_added_to_hass(self) -> None:
        """Register update listener."""
        self.hass.data[DOMAIN][self._entry_id]["update_listeners"].append(
            self._handle_state_update
        )

    @callback
    def _handle_state_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.hass.data[DOMAIN][self._entry_id][self._sensor_type]

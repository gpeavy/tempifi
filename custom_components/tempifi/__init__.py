"""The tempi.fi BLE Tracker integration."""
from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def select_best_key(updated_keys: list[int], last_seq: int, base_slot: int | None, buf_size: int | None) -> int | None:
    """Select the best slot key from the updated keys list using circular distance."""
    if not updated_keys:
        return None
    if len(updated_keys) == 1:
        return updated_keys[0]
    if last_seq == -1 or base_slot is None or buf_size is None:
        return max(updated_keys)

    # We have multiple updated keys.
    # Find the one that is the newest (largest forward distance from last_seq, within a reasonable threshold)
    idx_last = last_seq - base_slot
    candidates = []
    for k in updated_keys:
        idx_k = k - base_slot
        dist = (idx_k - idx_last) % buf_size
        candidates.append((dist, k))

    # Sort candidates by distance
    candidates.sort()

    reasonable = [c for c in candidates if c[0] < 100]
    if reasonable:
        # Return the candidate with the maximum distance within the reasonable range
        return reasonable[-1][1]
    else:
        # Reboot or outage occurred. Take the maximum key to get the newest value.
        return max(updated_keys)


def _update_state(hass: HomeAssistant, entry: ConfigEntry, target_slot: int, raw_data: dict) -> None:
    """Decode target slot payload and update stored state."""
    device_data = hass.data[DOMAIN][entry.entry_id]
    address = device_data["address"]

    slot_key = target_slot
    if slot_key not in raw_data and str(slot_key) in raw_data:
        slot_key = str(slot_key)

    payload = raw_data[slot_key]
    val1 = int.from_bytes(payload[0:2], byteorder="little", signed=False)
    val2 = int.from_bytes(payload[2:4], byteorder="little", signed=False)

    # Decode using standard SHT2x conversion equations
    humidity = -6.0 + 125.0 * (val1 / 65536.0)
    temp_c = -46.85 + 175.72 * (val2 / 65536.0)

    # Clamp and round
    humidity = max(0.0, min(100.0, round(humidity, 1)))
    temp_c = round(temp_c, 2)

    _LOGGER.debug(
        "Decoded %s (target_slot=%s): Temp=%.2f°C, Humidity=%.1f%%",
        address,
        target_slot,
        temp_c,
        humidity,
    )

    # Update stored state
    device_data["temperature"] = temp_c
    device_data["humidity"] = humidity

    # Notify the Home Assistant entities
    for listener in device_data["update_listeners"]:
        listener()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up tempi.fi BLE Tracker from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    address = entry.unique_id.upper()

    hass.data[DOMAIN][entry.entry_id] = {
        "address": address,
        "temperature": None,
        "humidity": None,
        "last_seq": -1,
        "prev_raw_data": None,
        "update_listeners": [],
    }

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    def _async_bluetooth_callback(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle incoming BLE advertisements."""
        raw_data = service_info.advertisement.manufacturer_data
        if not raw_data:
            return

        # Find all keys that contain a valid 4-byte payload.
        valid_keys = []
        for k in raw_data.keys():
            if isinstance(k, int) or (isinstance(k, str) and k.isdigit()):
                if len(raw_data[k]) == 4:
                    valid_keys.append(int(k))
        if not valid_keys:
            return

        device_data = hass.data[DOMAIN][entry.entry_id]
        now = dt_util.as_local(dt_util.utcnow())

        # Determine limits based on device address
        if address == "DC:74:B9:BA:77:FD":
            # Refrigerator
            base_slot = 20737
            buf_size = 3071
        elif address == "CC:FB:84:E7:73:91":
            # Freezer
            base_slot = 17153
            buf_size = 2845
        else:
            base_slot = None
            buf_size = None

        last_seq = device_data.get("last_seq", -1)
        prev_data = device_data.get("prev_raw_data")

        if prev_data is None:
            # 1. Startup initialization
            # Save the initial raw_data snapshot
            device_data["prev_raw_data"] = dict(raw_data)

            target_slot = None
            # Perform a one-time time alignment to locate the current active slot
            if address == "DC:74:B9:BA:77:FD" and base_slot is not None:
                # Refrigerator: Epoch At 2026-07-19 08:00:00 local time, sequence index was 23696.
                epoch = dt_util.as_local(datetime(2026, 7, 19, 8, 0, 0))
                delta_minutes = (now - epoch).total_seconds() / 60.0
                current_seq = 23696 + delta_minutes
                current_slot = (int(current_seq) - base_slot) % buf_size + base_slot
            elif address == "CC:FB:84:E7:73:91" and base_slot is not None:
                # Freezer: Epoch At 2026-07-19 08:05:00 local time, sequence index was 20565.
                epoch = dt_util.as_local(datetime(2026, 7, 19, 8, 5, 0))
                delta_minutes = (now - epoch).total_seconds() / 60.0
                current_seq = 20565 + delta_minutes
                current_slot = (int(current_seq) - base_slot) % buf_size + base_slot
            else:
                current_slot = None

            if current_slot is not None:
                for offset in range(15):
                    slot = (current_slot - offset - base_slot) % buf_size + base_slot
                    if slot in raw_data:
                        target_slot = slot
                        break
                    elif str(slot) in raw_data:
                        target_slot = slot
                        break

            if target_slot is None:
                target_slot = max(valid_keys)

            device_data["last_seq"] = int(target_slot)
            _update_state(hass, entry, int(target_slot), raw_data)
            return

        # 2. Subsequent callbacks (Real-time diff parsing)
        # Find which manufacturer data keys were updated/added in this packet
        updated_keys = []
        for k, v in raw_data.items():
            if isinstance(k, int) or (isinstance(k, str) and k.isdigit()):
                k_int = int(k)
                v_prev = prev_data.get(k_int) or prev_data.get(str(k_int))
                if v_prev is None or v_prev != v:
                    updated_keys.append(k_int)

        # Update cached raw data snapshot
        device_data["prev_raw_data"] = dict(raw_data)

        if not updated_keys:
            return

        # Choose the best updated slot key
        target_slot = select_best_key(updated_keys, last_seq, base_slot, buf_size)
        if target_slot is not None:
            device_data["last_seq"] = target_slot
            _update_state(hass, entry, target_slot, raw_data)

    # Subscribe to passive advertisements from this specific device address
    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_bluetooth_callback,
            {"address": address},
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

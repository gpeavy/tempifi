# tempi.fi BLE Tracker for Home Assistant

A lightweight Home Assistant custom component to passively track **tempi.fi** BLE temperature and humidity sensors. 

Because this integration is passive (it only listens for BLE advertisements), it does not establish active Bluetooth connections, ensuring that the sensor's battery life is preserved.

---

## Features
* **Passive BLE Tracking**: Low overhead, does not drain sensor battery.
* **Auto-Discovery**: Home Assistant will automatically detect nearby `tempi.fi` sensors when they advertise.
* **Device Registry Support**: Each sensor is represented as a single Device in Home Assistant containing both Temperature and Humidity entities.
* **Local Push**: Readings update in real-time as advertisements are broadcast (typically every minute).

---

## Installation

### Manual Installation
1. Copy the `custom_components/tempifi` directory from this repository into the `custom_components` directory in your Home Assistant configuration folder (e.g., `/config/custom_components/`).
2. Restart Home Assistant:
   * Go to **Developer Tools** -> **YAML** -> Click **Restart**.

### HACS Installation (Optional)
Once this repository is published on GitHub:
1. Open **HACS** in your Home Assistant interface.
2. Click the three dots in the top-right corner and select **Custom repositories**.
3. Paste your GitHub repository URL (e.g., `https://github.com/your-username/tempifi`), select **Integration** as the category, and click **Add**.
4. Download the integration through HACS and restart Home Assistant.

---

## Configuration

1. In Home Assistant, go to **Settings** -> **Devices & Services**.
2. If your tempi.fi sensor is broadcasting, it should appear in the **Discovered** section. Click **Configure**.
3. If it does not appear automatically:
   * Click **Add Integration** in the bottom right.
   * Search for **tempi.fi BLE Tracker**.
   * Enter the MAC address of the sensor manually (e.g., `CC:FB:84:E7:73:91`).

---

## Technical Details (Sensor Conversion)

This integration decodes the raw 4-byte manufacturer payload broadcasted by the sensor using standard **Sensirion SHT2x** register conversion equations:

* **Temperature ($^\circ$C)**:
  $$-46.85 + 175.72 \times \frac{\text{val}_2}{65536}$$
* **Humidity (%)**:
  $$-6.0 + 125.0 \times \frac{\text{val}_1}{65536}$$


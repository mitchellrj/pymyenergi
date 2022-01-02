"""Support for MyEnergi sensors."""
import logging

from homeassistant.const import CONF_USERNAME, DEVICE_CLASS_POWER, POWER_WATT
from homeassistant.helpers.entity import Entity

from .platform import ATTR_LAST_UPDATED, ATTR_MODE, ATTR_MODE_ECO, ATTR_MODE_ECO_PLUS, ATTR_MODE_FAST, ATTR_POWER, ATTR_VOLTAGE, DOMAIN, STATE_BOOSTING, STATE_CHARGING, STATE_COMPLETE, STATE_DELAYED, STATE_EV_WAITING, STATE_FAULT, STATE_NOT_CONNECTED, STATE_WAITING
from .myenergi import DeviceType, ZappiMode, ZappiStatus

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, device_config=None):
    """Set up the MyEnergi platform."""
    if device_config is None:
        return

    manager = hass.data[DOMAIN][device_config[CONF_USERNAME]]
    manager.setup_sensors_platform(async_add_entities)
    await manager.start()


STATE_MAP = {
    ZappiStatus.BOOSTING: STATE_BOOSTING,
    ZappiStatus.CHARGING: STATE_CHARGING,
    ZappiStatus.COMPLETE: STATE_COMPLETE,
    ZappiStatus.DELAYED: STATE_DELAYED,
    ZappiStatus.EV_WAITING: STATE_EV_WAITING,
    ZappiStatus.FAULT: STATE_FAULT,
    ZappiStatus.NOT_CONNECTED: STATE_NOT_CONNECTED,
    ZappiStatus.WAITING: STATE_WAITING,
}

MODE_MAP = {
    ZappiMode.ECO: ATTR_MODE_ECO,
    ZappiMode.ECO_PLUS: ATTR_MODE_ECO_PLUS,
    ZappiMode.FAST: ATTR_MODE_FAST,
}


class ZappiStatusSensor(Entity):
    """The entity class for the Zappi charging station status."""

    def __init__(self, zappi):
        """Initialize the Zappi Sensor."""
        self._device = zappi
        self._name = self._device.name
        self._icon = 'mdi:power-plug'
        self._state = None
        self._attributes = {}
        self.update()

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._state in (STATE_BOOSTING, STATE_CHARGING)

    @property
    def unique_id(self):
        return str(self._device)

    @property
    def should_poll(self):
        """Deactivate polling. Data updated by hub."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the binary sensor."""
        return self._name

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return None

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Get the unit of measurement."""
        return None

    @property
    def device_info(self):
        return {
            'identifiers': {
                (DOMAIN, self.unique_id)
            },
            'name': self._device.name,
            'manufacturer': 'MyEnergi',
            'model': self._device.device_type.value.title(),
            'via_device': (DOMAIN, str(self._device.hub)),
        }

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._attributes

    def update(self):
        """Get latest cached states from the device."""
        self._state = STATE_MAP.get(self._device.status, STATE_FAULT)
        self._attributes = {
            ATTR_MODE: MODE_MAP.get(self._device.mode, ATTR_MODE_ECO),
            ATTR_POWER: self._device.power,
            ATTR_VOLTAGE: self._device.voltage,
            ATTR_LAST_UPDATED: self._device.last_updated.isoformat(),
        }


POWER_ICONS = {
    DeviceType.POWER_GRID: 'mdi:transmission-tower',
    DeviceType.SOLAR_PANEL: 'mdi:solar-power',
    DeviceType.BATTERY: 'mdi:battery-minus',
}


class PowerSensorBase(Entity):
    """The entity class for a generation source."""

    state_class = "measurement"

    def __init__(self, device):
        self._icon = None
        self._name = None
        self._device = device
        self._unit = POWER_WATT
        self._device_class = DEVICE_CLASS_POWER
        self.update()

    @property
    def unique_id(self):
        return str(self._device)

    @property
    def should_poll(self):
        """Deactivate polling. Data updated by hub."""
        return False

    @property
    def unique_id(self):
        """Return the unique ID of the binary sensor."""
        return self.name

    @property
    def icon(self):
        if self._icon is None:
            self._icon = POWER_ICONS.get(self._device_type, 'mdi:power-plug')
        return self._icon

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Get the unit of measurement."""
        return self._unit

    @property
    def device_info(self):
        return {
            'identifiers': {
                (DOMAIN, self.unique_id)
            },
            'name': self._device.name,
            'manufacturer': 'MyEnergi',
            'model': self._device.device_type.value.title(),
            'via_device': (DOMAIN, str(self._device.hub)),
        }

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the binary sensor."""
        return self._attributes

    def update(self):
        """Get latest cached states from the device."""
        self._state = self._device.generators[self._generator_index]['power']
        self._attributes = {ATTR_LAST_UPDATED: self._device.last_updated.isoformat()}


class GenerationSensor(PowerSensorBase):
    """The entity class for a generation source."""

    def __init__(self, device, generator_index):
        self._generator_index = generator_index
        self._device_type = device.generators[self._generator_index]['type']
        PowerSensorBase.__init__(self, device)

    @property
    def name(self):
        """Return the name of the device."""
        if self._name is None:
            device_type_title = self._device.name
            generator_type_title = self._device_type.value.title()
            self._name = '{} {} power from {}'.format(device_type_title, str(self._device), generator_type_title)
        return self._name


class ZappiPowerSensor(PowerSensorBase):
    """The entity class for a Zappi charging station power."""

    _device_type = DeviceType.ZAPPI

    @property
    def name(self):
        if self._name is None:
            self._name = '{} power'.format(self._device.name)
        return self._name


    @property
    def is_on(self):
        """Return True if entity is on."""
        return STATE_MAP.get(self._device.status, STATE_FAULT) in (STATE_BOOSTING, STATE_CHARGING) and self._state > 0

    def update(self):
        """Get latest cached states from the device."""
        self._state = self._device.power
        self._attributes = {
            ATTR_LAST_UPDATED: self._device.last_updated.isoformat(),
        }
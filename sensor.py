"""Support for MyEnergi sensors."""
import logging

from homeassistant.const import CONF_USERNAME, DEVICE_CLASS_POWER, POWER_WATT
from homeassistant.helpers.entity import Entity

from .platform import ATTR_MODE, ATTR_MODE_ECO, ATTR_MODE_ECO_PLUS, ATTR_MODE_FAST, ATTR_POWER, ATTR_VOLTAGE, DOMAIN, STATE_BOOSTING, STATE_CHARGING, STATE_COMPLETE, STATE_DELAYED, STATE_EV_WAITING, STATE_FAULT, STATE_NOT_CONNECTED, STATE_WAITING
from .myenergi import DeviceType, ZappiMode, ZappiStatus

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, device_config=None):
    """Set up the MyEnergi platform."""
    if device_config is None:
        _LOGGER.info('MyEnergi config is none')
        return

    manager = hass.data[DOMAIN][device_config[CONF_USERNAME]]
    manager.setup_sensors_platform(async_add_entities)
    _LOGGER.info('Starting MyEnergi manager')
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
        self._zappi = zappi
        self._name = 'Zappi z' + str(zappi.serial)
        self._icon = 'mdi:power-plug'
        self._state = None
        self._attributes = {}
        self.update()

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._state in (STATE_BOOSTING, STATE_CHARGING)

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
            'identifiers': (DOMAIN, 'z' + str(self._zappi.serial))
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._attributes

    def update(self):
        """Get latest cached states from the device."""
        self._state = STATE_MAP.get(self._zappi.status, STATE_FAULT)
        self._attributes = {
            ATTR_MODE: MODE_MAP.get(self._zappi.mode, ATTR_MODE_ECO),
            ATTR_POWER: self._zappi.power,
            ATTR_VOLTAGE: self._zappi.voltage,
        }


class ZappiPowerSensor(Entity):
    """The entity class for a Zappi charging station power."""

    def __init__(self, zappi):
        """Initialize the Zappi power Sensor."""
        self._zappi = zappi
        self._name = 'Zappi z{} power usage'.format(zappi.serial)
        self._icon = 'mdi:power-plug'
        self._unit = POWER_WATT
        self._device_class = DEVICE_CLASS_POWER
        self.update()

    @property
    def is_on(self):
        """Return True if entity is on."""
        return STATE_MAP.get(self._zappi.status, STATE_FAULT) in (STATE_BOOSTING, STATE_CHARGING) and self._state > 0

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
        return self._device_class

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
        return self._unit

    @property
    def device_info(self):
        return {
            'identifiers': (DOMAIN, 'z' + str(self._zappi.serial))
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes of the binary sensor."""
        return self._attributes

    def update(self):
        """Get latest cached states from the device."""
        self._state = self._zappi.power
        self._attributes = {}

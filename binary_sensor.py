"""Support for MyEnergi sensors."""
import logging

from homeassistant.const import CONF_USERNAME
from homeassistant.components.binary_sensor import BinarySensorEntity, DEVICE_CLASS_PRESENCE

from .platform import DOMAIN
from .myenergi import ZappiStatus

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, device_config=None):
    """Set up the MyEnergi platform."""
    if device_config is None:
        return

    manager = hass.data[DOMAIN][device_config[CONF_USERNAME]]
    manager.setup_binary_sensors_platform(async_add_entities)
    await manager.start()


class ZappiPresenceSensor(BinarySensorEntity):
    """The entity class for the Zappi charging station presence sensor."""

    def __init__(self, zappi):
        """Initialize the Zappi Sensor."""
        self._device = zappi
        self._name = 'Zappi z{} car connected'.format(self._device.serial)
        self._icon = 'mdi:car'
        self._state = None
        self._device_class = DEVICE_CLASS_PRESENCE
        self._attributes = {}
        self.update()

    @property
    def unique_id(self):
        return str(self._device)

    @property
    def is_on(self):
        """Return True if entity is on."""
        return self._device.status not in (ZappiStatus.FAULT, ZappiStatus.NOT_CONNECTED)

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
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Get the unit of measurement."""
        return None

    @property
    def device_info(self):
        return {
            'identifiers': (DOMAIN, self.unique_id)
        }

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._attributes

    def update(self):
        """Get latest cached states from the device."""
        self._attributes = {}

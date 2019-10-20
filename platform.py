### HA support

"""Support for MyEnergi devices."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
import voluptuous as vol

from homeassistant.const import (
    CONF_USERNAME, CONF_DEVICES, CONF_PASSWORD)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

from . import myenergi

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'myenergi'

# Status states
STATE_NOT_CONNECTED = 'not-connected'
STATE_EV_WAITING = 'ev-waiting'
STATE_WAITING = 'waiting'
STATE_CHARGING = 'charging'
STATE_BOOSTING = 'boosting'
STATE_COMPLETE = 'complete'
STATE_DELAYED = 'delayed'
STATE_FAULT = 'fault'
# Modes
ATTR_MODE = 'mode'
ATTR_MODE_FAST = 'fast'
ATTR_MODE_ECO = 'eco'
ATTR_MODE_ECO_PLUS = 'eco-plus'
# other attributes
ATTR_POWER = 'power'
ATTR_VOLTAGE = 'voltage'

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: DEVICE_SCHEMA,
}, extra=vol.ALLOW_EXTRA)


class MyEnergiManager:

    SCAN_INTERVAL = timedelta(seconds=5)

    def __init__(self, hass, username, password):
        self.hass = hass
        self.hub = myenergi.Hub(username, password)
        self._zappis_seen = {}
        self.async_add_entities = None
        self._started = False
    
    def setup_sensors_platform(self, async_add_entities):
        self.async_add_entities = async_add_entities

    async def async_update_items(self):
        all_new_sensors = []
        try:
            with async_timeout.timeout(4):
                zappis = await self.hub.async_fetch_zappis()
        except asyncio.TimeoutError:
            _LOGGER.error('Fetching Zappis timed out')
            return

        from .sensor import ZappiStatusSensor, ZappiPowerSensor

        for zappi in zappis:
            if zappi.serial in self._zappis_seen:
                for s in self._zappis_seen[zappi.serial]:
                    self.hass.async_create_task(s.async_update_ha_state())
                continue

            new_sensors = [
                ZappiStatusSensor(zappi),
                ZappiPowerSensor(zappi),
            ]
            self._zappis_seen[zappi.serial] = new_sensors

            all_new_sensors.extend(new_sensors)

        self.async_add_entities(all_new_sensors)

        # Removing items? uhhh. TODO

    async def start(self):
        """Start updating sensors from the hub on a schedule."""
        # but only if it's not already started, and when we've got the
        # async_add_entities method
        if self._started or self.async_add_entities is None:
            _LOGGER.info('Starting MyEnergi manager failed: {}. {}'.format(self._started, self.async_add_entities))
            return

        self._started = True
        _LOGGER.info(
            "Starting MyEnergi polling loop with %s second interval",
            self.SCAN_INTERVAL.total_seconds(),
        )

        async def async_update(now):
            """Will update data."""

            await self.async_update_items()

            async_track_point_in_utc_time(
                self.hass, async_update, utcnow() + self.SCAN_INTERVAL
            )

        await async_update(None)


def setup(hass, config):
    """Set up MyEnergi devices."""
    hass.data[DOMAIN] = {}
    device_info = config.get(DOMAIN, {})
    hass.data[DOMAIN][device_info[CONF_USERNAME]] = MyEnergiManager(hass, device_info[CONF_USERNAME], device_info[CONF_PASSWORD])
    device_info = dict(device_info)
    device_info.pop(CONF_PASSWORD)
    discovery.load_platform(hass, 'sensor', DOMAIN, device_info, config)
    return True
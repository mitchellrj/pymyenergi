import asyncio
import datetime
import enum
import logging
import math
import sys
from urllib.parse import urljoin, urlparse, urlunparse
import weakref

import pytz
import requests
from requests.auth import HTTPDigestAuth


logger = logging.getLogger(__name__)
api_root = "https://s7.myenergi.net"


logging.basicConfig(level=logging.DEBUG)


def get_uri(m, params=None, order=None, sep=None):
    if params is None:
        params = {}
    if order is None:
        order = sorted(params.keys())
    if sep is None:
        sep = "-"

    qs = "-" + sep.join([params[k] for k in order])
    root_parts = urlparse(api_root)
    return urlunparse(
        (
            root_parts.scheme,
            root_parts.netloc,
            urljoin(root_parts.path, "/cgi-{}{}".format(m, qs)),
            "",
            "",
            "",
        )
    )


class Hub:

    def __init__(self, serial, password):
        self.session = requests.session()
        self.session.auth = HTTPDigestAuth(serial, password)
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"})
        self._zappis = {}
        self._harvis = {}

    def async_request(self, m, params, order=None, sep=None):
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(None, self.request, m, params, order, sep)

    def request(self, m, params, order=None, sep=None):
        # ugh. I want to use aiohttp, but the digest authentication makes this
        # painful
        resp = self.session.get(get_uri(m, params, order, sep))
        resp.raise_for_status()
        return resp.json()

    async def async_fetch_zappis(self):
        response = await self.async_request('jstatus', {'id': 'Z'})
        for zappi_data in response.get('zappi', []):
            z = Zappi.from_json(zappi_data, self)
            if z.serial in self._zappis:
                continue
            self._zappis[z.serial] = z

        return list(self._zappis.values())

    async def async_fetch_harvis(self):
        response = await self.async_request('jstatus', {'id': 'H'})
        for harvi_data in response.get('harvi', []):
            h = Harvi.from_json(harvi_data, self)
            if h.serial in self._harvis:
                continue
            self._harvis[h.serial] = h
        return list(self._harvis.values())

    async def async_fetch_eddis(self):
        response = await self.async_request('jstatus', {'id': 'E'})
        for eddi_data in response.get('eddi', []):
            pass
        return []


class DeviceType(enum.Enum):

    HARVI = 'harvi'
    BATTERY = 'battery'
    SOLAR_PANEL = 'solar'
    OVERALL = 'overall'
    POWER_GRID = 'grid'
    HOME = 'home'
    EDDI = 'eddi'
    ZAPPI = 'zappi'


class HeaterType(enum.Enum):

    HEATER_1 = 1
    HEATER_2 = 2
    RELAY_1 = 5
    RELAY_2 = 6


class ZappiStatus(enum.Enum):

    NOT_CONNECTED = 0
    EV_WAITING = 1
    WAITING = 2
    CHARGING = 3
    BOOSTING = 4
    COMPLETE = 5
    DELAYED = 6
    FAULT = 255


class ZappiMode(enum.Enum):

    NO_CHANGE = 0
    FAST = 1
    ECO = 2
    ECO_PLUS = 3


class ZappiBoostMode(enum.Enum):

    NO_CHANGE = 0
    CANCEL_NON_TIMED = 1
    CANCEL_ALL = 2
    START_MANUAL = 3
    START_SMART = 4


class CommandStatus(enum.Enum):

    IN_PROGRESS = 1
    FAILED = 2
    FINISHED = 3


class Schedule:

    def __init__(self, heater_type, slot, sub_slot, start_time, duration,
                 days):
        pass

    @classmethod
    def from_json(cls, data):
        cls(
            HeaterType(math.floor(data['slt'] / 10)),
            data['slt'],
            data['slt'] % 10,
            datetime.time(data['bsh'], data['bsm']),
            datetime.timedelta(0, data['bdh'], data['bdm']),
            # True/False for each day of the week, starting with Monday
            [d == '1' for d in data['bdd'][1:]]
        )


class Device:

    device_type = None
    device_serial_prefix = None
    device_map_key = None

    def __init__(self, serial, hub=None):
        self.__hub = weakref.ref(hub) if hub else None
        self.serial = serial
        self.last_updated = None
    
    @property
    def hub(self):
        return self.__hub() if self.__hub else None

    def __eq__(self, other):
        return self.serial == other.serial

    def __str__(self):
        return self.device_serial_prefix + str(self.serial)

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, self.serial)

    def _update_from_json(self, data):
        self.generators = []
        print(data)
        for n in range(1, 6):
            g_name = 'ectt{}'.format(n)
            if g_name not in data:
                break
            if data[g_name].lower() in ('none', 'internal load'):
                continue
            try:
                g = {
                    'type': DeviceType(data['ectt{}'.format(n)].lower()),
                    'power': data['ectp{}'.format(n)]
                }
                self.generators.append(g)
            except (ValueError) as e:
                # unsupported device type
                #logger.warning('Unsupported device type {}'.format(data['ectt{}'.format(n)]))
                logger.exception(e)
                continue
        dt = datetime.datetime.strptime(
            "{}T{}".format(data["dat"], data["tim"]), "%d-%m-%YT%H:%M:%S"
        )
        self.last_updated = dt.replace(tzinfo=pytz.UTC)

    @classmethod
    def from_json(cls, data, hub=None):
        device_map = getattr(hub, '_{}'.format(cls.device_map_key))
        if hub is not None and data['sno'] in device_map:
            z = device_map[data['sno']]
        else:
            z = cls(data['sno'], hub)
        z._update_from_json(data)
        return z


class Harvi(Device):

    device_type = DeviceType.HARVI
    device_serial_prefix = 'H'
    device_map_key = 'harvis'


class Zappi(Device):

    device_type = DeviceType.ZAPPI
    device_serial_prefix = 'Z'
    device_map_key = 'zappis'

    def _get_status(self, status, operating_mode):
        if operating_mode == "A":
            return ZappiStatus.NOT_CONNECTED
        elif operating_mode == "B1":
            if status in (1, 2):
                return ZappiStatus.WAITING
            elif status == 5:
                return ZappiStatus.COMPLETE
            return ZappiStatus.EV_WAITING
        elif operating_mode == "B2":
            if status == 5:
                return ZappiStatus.COMPLETE
            return ZappiStatus.DELAYED
        elif operating_mode == "C1":
            if status == 3:
                return ZappiStatus.CHARGING
            elif status == 4:
                return ZappiStatus.BOOSTING
            elif status == 5:
                return ZappiStatus.COMPLETE
            return ZappiStatus.WAITING
        elif operating_mode == "C2":
            if status == 4:
                return ZappiStatus.BOOSTING
            elif status == 5:
                return ZappiStatus.COMPLETE
            return ZappiStatus.CHARGING
        elif operating_mode == "F":
            return ZappiStatus.FAULT
        return ZappiStatus.NOT_CONNECTED

    async def async_set_mode(self, mode=None, boost=None, kwh=0, target_time=None):
        if mode is None:
            mode = ZappiMode.NO_CHANGE
        if boost is None:
            boost = ZappiBoostMode.NO_CHANGE
        if target_time is None:
            target_time = '0000'
        return self.hub.request(
            'zappi-mode',
            {
                'id': self.serial,
                'mode': mode.value,
                'boost': boost.value,
                'kwh': kwh,
                'targetTime': target_time
            },
            ['id', 'mode', 'boost', 'kwh', 'targetTime']
        )

    async def get_timed_boost(self):
        return self.hub.request('boost-time', {'id': self.serial})

    def _update_from_json(self, data):
        super(Zappi, self)._update_from_json(data)
        self.frequency = data["frq"]
        self.phase = data["pha"]
        self.serial = data["sno"]
        self.status = self._get_status(data["sta"], data["pst"])
        self.voltage = data["vol"]
        self.power = data.get("div", 0)
        self.priority = data["pri"]
        if data["cmt"] <= 10:
            self.command_status = CommandStatus.IN_PROGRESS
        elif data["cmt"] == 253:
            self.command_status = CommandStatus.FAILED
        else:
            self.command_status = CommandStatus.FINISHED
        self.mode = ZappiMode(data["zmo"])
        self.remaining_manual_boost = data.get("tbk", 0)
        self.remaining_smart_boost = data.get("sbk", 0)
        self.current_charge = data.get("che", 0)
        self.minimum_green_level = data.get("mgl", 0)
        self.smart_boost_target_time_minutes = (60 * data.get("sbh", 0)) + data.get("sbm", 0)


async def async_main(serial, password):
    hub = Hub(serial, password)
    zappis = await hub.async_fetch_zappis()
    harvis = await hub.async_fetch_harvis()
    print(zappis[0])
    print(harvis[0])
    print(zappis[0].generators)
    print(harvis[0].generators)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    serial = argv[0]
    password = argv[1]

    asyncio.run(async_main(serial, password))


if __name__ == '__main__':
    main()

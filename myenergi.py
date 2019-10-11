import datetime
import enum
import json
import sys
from urllib.parse import urljoin, urlparse, urlunparse

import pytz
import requests
from requests.auth import HTTPDigestAuth


api_root = 'https://s7.myenergi.net'
serial = sys.argv[1]
password = sys.argv[2]


def get_uri(m, params=None, order=None, sep=None):
    if params is None:
        params = {}
    if order is None:
        order = sorted(params.keys())
    if sep is None: sep = '-'

    qs = '-' + sep.join([params[k] for k in order])
    root_parts = urlparse(api_root)
    return urlunparse((
        root_parts.scheme,
        root_parts.netloc,
        urljoin(root_parts.path, '/cgi-{}{}'.format(m, qs)),
        '',
        '',
        ''
    ))


s = requests.session()
s.auth = HTTPDigestAuth(serial, password)
s.headers.update({
    'Accept': 'application/json',
    'Content-Type': 'application/json'
})


def request(m, params):
    resp = s.get(get_uri(m, params))
    resp.raise_for_status()
    return resp.json()


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

    FAST = 1
    ECO = 2
    ECO_PLUS = 3


class CommandStatus(enum.Enum):

    IN_PROGRESS = 1
    FAILED = 2
    FINISHED = 3


class Zappi:

    def __init__(self, serial):
        self.serial = serial
        self.last_updated = None

    def _get_status(self, status, operating_mode):
        if operating_mode == 'A':
            return ZappiStatus.NOT_CONNECTED
        elif operating_mode == 'B1':
            if status in (1, 2):
                return ZappiStatus.WAITING
            elif status == 5:
                return ZappiStatus.COMPLETE
            return ZappiStatus.EV_WAITING
        elif operating_mode == 'B2':
            if status == 5:
                return ZappiStatus.COMPLETE
            return ZappiStatus.DELAYED
        elif operating_mode == 'C1':
            if status == 3:
                return ZappiStatus.CHARGING
            elif status == 4:
                return ZappiStatus.BOOSTING
            elif status == 5:
                return ZappiStatus.COMPLETE
            return ZappiStatus.WAITING
        elif operating_mode == 'C2':
            if status == 4:
                return ZappiStatus.BOOSTING
            elif status == 5:
                return ZappiStatus.COMPLETE
            return ZappiStatus.CHARGING
        elif operating_mode == 'F':
            return ZappiStatus.FAULT
        return ZappiStatus.NOT_CONNECTED

    def update(self, data):
        dt = datetime.datetime.strptime('{}T{}'.format(data['dat'], data['tim']), '%d-%m-%YT%H:%M%:S')
        self.last_updated = dt.replace(tzinfo=pytz.UTC)
        self.frequency = data['frq']
        self.power_watts = data['grd']
        self.phase = data['pha']
        self.serial = data['sno']
        self.status = self._get_status(data['sta'], data['pst'])
        self.voltage = data['vol']
        self.priority = data['pri']
        if data['cmt'] <= 10:
            self.command_status = CommandStatus.IN_PROGRESS
        elif data['cmt'] == 253:
            self.command_status = CommandStatus.FAILED
        else:
            self.command_status = CommandStatus.FINISHED
        self.mode = ZappiMode(data['zmo'])
        self.remaining_manual_boost = data['tbk']
        self.remaining_smart_boost = data['sbk']
        self.current_charge = data['che']
        self.minimum_green_level = data['mgl']
        self.smart_boost_target_time_minutes = (60 * data['sbh']) + data['sbm']

# Z = zappi
# E = eddi
# H = harvi
print(json.dumps(request('jstatus', {'id': 'Z'}),indent=2))
print(json.dumps(request('jstatus', {'id': 'E'}),indent=2))
print(json.dumps(request('jstatus', {'id': 'H'}),indent=2))


{
  "zappi": [
    {
      "dat": "07-10-2019",
      "tim": "21:04:29",
      "ectp1": -8,
      "ectp2": -29,
      "ectt1": "None",
      "ectt2": "None",
      "frq": 49.95,
      "grd": 632,
      "pha": 1,
      "sno": 12016875,
      "sta": 1,
      "vol": 241.5,
      "pri": 1,
      "cmt": 254,
      "zmo": 1,
      "tbk": 5,
      "che": 9,
      "pst": "B2",
      "mgl": 50,
      "sbh": 17,
      "sbk": 5
    }
  ]
}

# dat = date (UTC)
# tim = time (UTC)
# ectp2 = power (source)
# ectt2 = type (source)
# frq = frequency (Hz)?
# grd = grid power
# pha = phase
# sno = unit serial number (prefix with Z)
# vol = voltage
# pri = priority
# cmt = command status (<=10 == in progress, 253 == failed, other == finished)
# mgl = minimum green level
# tbk = remaining manual boost
# sbk = remaining smart boost
# che = current charge
# zmo = zappi mode (1=fast, 2=eco, 3=eco+)
# command status
# boost status
# smart boost target time = 60 * (t.sbh || 0) + (t.sbm || 0)
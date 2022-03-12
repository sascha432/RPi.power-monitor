#
# Author: sascha_lammers@gmx.de
#

from SDL_Pi_INA3221.Calibration import Calibration as InaCalibration
from SDL_Pi_INA3221 import INA3211_CONFIG
from Config import (Type, Path, Param, DictType, TimeConverter, MarginConverter, RangeConverter, ListConverter, EnumConverter, Base, ListBase, ItemBase)
from . import Enums
from .Gui import Gui
import socket

class App(Base):

    VERSION = '0.0.2'

    blit = False

    config_dir = (None, (Param.ReadOnly,))
    config_file = ('{config_dir}/config.json', (Param.ReadOnly,))
    database_file = '{config_dir}/power_monitor.db'

    pid_file = '{config_dir}/power_monitor.pid'

    store_energy_interval = TimeConverter.value(60)

    idle_check_interval = TimeConverter.value(2, 's')
    idle_check_cmd = '/usr/bin/xset -display ${DISPLAY} -q'
    # multi line regexp with ignore case
    idle_check_monitor_on = '^\s*monitor is on'
    idle_check_monitor_off = '^\s*monitor is off'

    headless = False
    verbose = False
    daemon = False
    ignore_warnings = 0

    def __init__(self, struct={}):
        Base.__init__(self, struct)

    _debug = False
    _terminate = None
    def _debug_exception(self, e):
        if self._debug:
            if self._terminate:
                self._terminate.set()
            raise e

class ChannelList(ListBase):
    def __init__(self, struct):
        ListBase.__init__(self, struct)

class Channel(ItemBase):

    number = (lambda path: path.index + 1, (Param.ReadOnly,))
    index = (lambda path: path.index, (Param.ReadOnly,))
    enabled = False
    aggregate_power = True
    voltage = (None, (float))
    color = (None, (str,))
    hline_color = (None, (str,))

    COLOR_AGGREGATED_POWER = 'red'
    COLOR_MAX_CURRENT = 'red'
    COLOR_MIN_CURRENT = 'blue'

    def __init__(self, struct, index):
        ItemBase.__init__(self, struct, index)

    def __int__(self):
        return self.index

    def _color_for(self, type):
        if type=='Psum':
            return Channel.COLOR_AGGREGATED_POWER
        if type=='hline':
            return self.hline_color
        return self.color

class YLimits(Base):

    def __init__(self):
        Base.__init__(self, {})

    # fixed y limits for the channel and margins are ignored
    # if the value exceeds the limit, the plot will cut it off at the fixed limit
    voltage_max = (None, (float, int, None,))
    voltage_min = (None, (float, int, None,))

    # TODO
    # keep max. voltage limit until changing the view or restarting
    voltage_keep_max  = (False, (bool,))
    voltage_keep_min = (False, (bool,))

    # TODO
    current_max = (None, (float, int, None,))
    current_min = (None, (float, int, None,))
    power_max = (None, (float, int, None,))
    power_min = (None, (float, int, None,))

class Plot(Base):
    refresh_interval = TimeConverter.value(250, 'ms')
    idle_refresh_interval = TimeConverter.value(30000, 'ms')
    max_values = 8192
    max_time = TimeConverter.value(900)

    line_width = 3.5
    grid_line_width = 1.0
    font_size = 20.5

    display_energy = Enums.DISPLAY_ENERGY.AH
    display_top_values_mean_time = TimeConverter.value(5)

    current_top_margin = MarginConverter.top_value(5),                  # +5% / 105%
    current_bottom_margin = MarginConverter.bottom_value(10),           # -10% / 90%

    power_top_margin = MarginConverter.top_value(5),
    power_bottom_margin = MarginConverter.bottom_value(10),

    voltage_top_margin = MarginConverter.top_value(1),
    voltage_bottom_margin = MarginConverter.bottom_value(1),

    def __init__(self, struct):
        Base.__init__(self, struct)

class PlotCompression(Base):

    min_records = 64
    uncompressed_time = TimeConverter.value(60)

    def __init__(self, struct={}):
        Base.__init__(self, struct)

class Gui(Base):

    title = 'Power Monitor'
    fullscreen = True
    display = '$DISPLAY'

    # <width>x<width>[x<scaling=1.0>[x<dpi=72*scaling>]]
    # dpi affects the plot only. negative values are not scaled
    geometry = "800x480x1.0x72"
    color_scheme = Enums.COLOR_SCHEME.DEFAULT

    def __init__(self, struct={}):
        Base.__init__(self, struct)

class KeyBindings(Base):

    toggle_fullscreen = ('<F11>', (str,))
    end_fullscreen = ('<Escape>', (str,))
    menu = ('<F1>', (str,))
    plot_visibility = ('<F2>', (str,))
    plot_primary_display = ('<F3>', (str,))
    plot_display_energy= ('<F4>', (str,))
    toggle_debug = ('<Control-F9>', (str,))
    reload_config = ('<F11>', (str,))
    reset_plot = ('<Control-F10>', (str,))
    raw_sensor_values = ('<Control-r>', (str,))
    quit = ('<Alt-F4>', (str,))

    def __init__(self, struct={}):
        Base.__init__(self, struct)

class Ina3221(Base):

    i2c_address = 0x040
    auto_mode_sensor_values_per_second = (0.0, (float, int, None,))
    averaging_mode = INA3211_CONFIG.AVERAGING_MODE.x16
    vshunt_conversion_time = INA3211_CONFIG.VSHUNT_CONVERSION_TIME.time_1100_us
    vbus_conversion_time = INA3211_CONFIG.VBUS_CONVERSION_TIME.time_1100_us

    def __init__(self, struct={}):
        Base.__init__(self, struct)

class Influxdb(Base):

    host = (None, (str,))
    port = RangeConverter.value(8086, range(0, 65535), (int,)),
    username = 'root'
    password = 'root'
    database = 'ina3221'
    tags_host = socket.gethostname()

    def __init__(self, struct={}):
        Base.__init__(self, struct)

class Mqtt(Base):

    device_name = socket.gethostname()
    sensor_name = 'INA3221'

    host = (None, (str,))
    port = RangeConverter.value(1883, range(0, 65535), (int,))
    keepalive = TimeConverter.value(60)
    qos = ListConverter.value(0, [0, 1, 2], (int,))

    topic_prefix = 'home'
    auto_discovery = True
    auto_discovery_prefix = 'homeassistant'

    update_interval = TimeConverter.value(60)

    payload_online = '1'
    payload_offline = '0'

    # constants

    STATUS_TOPIC = '{topic_prefix}/{device_name}/{sensor_name}/status'
    CHANNEL_TOPIC = '{topic_prefix}/{device_name}/{sensor_name}/ch{channel}'

    AUTO_DISCOVERY_TOPIC = '{auto_discovery_prefix}/sensor/{device_name}_{sensor_name}_ch{channel}_{entity}/config'
    MODEL = 'RPI.ina3221-power-monitor'
    MANUFACTURER = 'KFCLabs'
    ENTITIES = { 'U': 'V', 'P': 'W', 'I': 'A', 'EP': 'kWh', 'EI': 'Ah' }
    AGGREGATED = [ ('P', 'W'), ('E', 'kWh') ]

    def __init__(self, struct={}):
        Base.__init__(self, struct)

    def _is_key_valid(self, name):
        if not Path._is_key_valid(name):
            return False
        return not name.startswith('get_')

    def _format_topic(self, topic, channel='-', entity='-', ts=''):
        return topic.format(topic_prefix=self.topic_prefix, auto_discovery_prefix=self.auto_discovery_prefix, device_name=self.device_name, sensor_name=self.sensor_name, channel=channel, entity=entity, ts=ts)

    def get_channel_topic(self, channel):
        return self._format_topic(self.CHANNEL_TOPIC, channel=channel)

    def get_status_topic(self):
        return self._format_topic(self.STATUS_TOPIC)

    def get_auto_discovery_topic(self, channel, entity):
        return self._format_topic(self.AUTO_DISCOVERY_TOPIC, channel=channel, entity=entity)


class Calibration(Base):

    vshunt_raw_offset = 0       # raw shunt sensor offset
    vshunt_multiplier = 1.0     # shunt voltage multiplier (effectively current divider)
    vbus_multiplier = 1.0       # vbus voltagte multiplier
    shunt = 100.0               # shunt value in mOhm

    def __init__(self, struct={}):
        Base.__init__(self, struct)
        self._multipliers = {}
        self._channel = None

    def _update_multipliers(self):
        self._multipliers.update({
            'mA': InaCalibration.RAW_VSHUNT_TO_MILLIVOLT / (self.shunt / (self.vshunt_multiplier * 1000.0)),
            'A': InaCalibration.RAW_VSHUNT_TO_MILLIVOLT / (self.shunt / self.vshunt_multiplier),
            'mV': self.vbus_multiplier * InaCalibration.RAW_VBUS_TO_VOLT * 0.001,
            'V': self.vbus_multiplier * InaCalibration.RAW_VBUS_TO_VOLT
        })

    def __setattr__(self, key, val):
        # print("__setattr__", key, val)

        if key in('_channel', '_multipliers', 'vshunt_raw_offset'):
            object.__setattr__(self, key, val)
            return
        if key in('shunt', 'vshunt_multiplier', 'vbus_multiplier'):
            object.__setattr__(self, key, val)
            if self._channel!=None:
                self._update_multipliers()
            return

        Base.__setattr__(self, key, val)

    def __dir__(self):
        return ['vshunt_raw_offset', 'vshunt_multiplier', 'vbus_multiplier', 'shunt']

    # returns current in mA or A for the given raw shut voltage
    def get_current_from_shunt(self, raw_value, for_unit='mA'):
        # dividing the shunt equals multiplying the voltage
        # V = I * (R / Cvbus) == R = (Cvbus * V) / I
        return self._multipliers[for_unit] * (raw_value + self.vshunt_raw_offset)

    # unit 'V' or 'mV'
    def get_vbus_voltage(self, raw_value, unit='V'):
        return self._multipliers[unit] * raw_value

class Channels(list):

    def __init__(self):
        list.__init__([])

class ChannelCalibration(object):
    def __init__(self, config):
        self._config = config

    def __getitem__(self, key):
        return self._config.channels[key].calibration

    def __contains__(self, key):
        return key in self._config.channels

    def __len__(self):
        return len(self._config.channels)

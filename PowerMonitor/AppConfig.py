#
# Author: sascha_lammers@gmx.de
#

import Config
import SDL_Pi_INA3221
from Config import (Type, Path)

class App(Config.Base):

    VERSION = '0.0.1'

    config_dir = ('.', (Config.Param.ReadOnly,))
    config_file = ('{config_dir}/config.json', (Config.Param.ReadOnly,))
    energy_storage_file = '{config_dir}/energy.json'

    headless = False
    verbose = False
    daemon = False

    def __init__(self, struct={}):
        Config.Base.__init__(self, struct)

    _debug = False
    _terminate = None
    def _debug_exception(self, e):
        if self._debug:
            if self._terminate:
                self._terminate.set()
            raise e

class ChannelList(Config.ListBase):
    def __init__(self, struct):
        Config.ListBase.__init__(self, struct)

class Channel(Config.ItemBase):

    number = (lambda path: path.index + 1, (Config.Param.ReadOnly,))
    index = (lambda path: path.index, (Config.Param.ReadOnly,))
    enabled = False
    voltage = (None, (float))

    def __init__(self, struct, index):
        Config.ItemBase.__init__(self, struct, index)

    def __int__(self):
        return self.index

    def _color_for(self, type):
        if type=='Psum':
            return AppConfig.FG_CHANNEL0
        return self.color


class Plot(Config.Base):
    refresh_interval = Config.TimeConverter.value(250, 'ms')
    idle_refresh_interval = Config.TimeConverter.value(2500, 'ms')
    max_values = 512
    max_time = Config.TimeConverter.value(300)
    line_width = 1.0

    display_energy = ('Wh', (str), ['Wh', 'Ah'])

    main_top_margin = Config.MarginConverter.top_value(5),
    main_bottom_margin = Config.MarginConverter.bottom_value(20),
    main_current_rounding = 0.25
    main_power_rounding = 2.0

    main_y_limit_scale_time = Config.TimeConverter.value(5.0)
    main_y_limit_scale_value = 0.05

    voltage_top_margin = Config.MarginConverter.top_value(0.5),
    voltage_bottom_margin = Config.MarginConverter.bottom_value(0.5),

    def __init__(self, struct):
        Config.Base.__init__(self, struct)

class PlotCompression(Config.Base):

    min_records = 200
    uncompressed_time = Config.TimeConverter.value(60)

    def __init__(self, struct={}):
        Config.Base.__init__(self, struct)

class Gui(Config.Base):

    fullscreen = True
    display = '$DISPLAY'

    def __init__(self, struct={}):
        Config.Base.__init__(self, struct)

class Backlight(Config.Base):

    def __init__(self, struct=Config.DictType({
            'gpio': Config.Param(None, (int, None))
        })):
        Config.Base.__init__(self, struct)

class Mqtt(Config.Base):

    device_name = 'PowerMonitor'
    sensor_name = 'INA3221'

    host = (None, str)
    port = Config.RangeConverter.value(1883, range(0, 65535), (int,))
    keepalive = Config.TimeConverter.value(60)
    qos = (2, (int,), [0, 1, 2])

    topic_prefix = 'home'
    auto_discovery = True
    auto_discovery_prefix = 'homeassistant'

    update_interval = Config.TimeConverter.value(60)

    payload_online = '1'
    payload_offline = '0'

    motion_topic = '{topic_prefix}/{device_name}/motion_detection'
    motion_payload = (None, (int, str), lambda val, param: str(val))
    motion_retain = False
    motion_repeat_delay = Config.TimeConverter.value(30)

    # consts

    STATUS_TOPIC = '{topic_prefix}/{device_name}/{sensor_name}/status'
    CHANNEL_TOPIC = '{topic_prefix}/{device_name}/{sensor_name}/ch{channel}'

    AUTO_DISCOVERY_TOPC = '{auto_discovery_prefix}/sensor/{device_name}_{sensor_name}_ch{channel}_{entity}/config'
    MODEL = 'RPI.ina3221-power-monitor'
    MANUFACTURER = 'KFCLabs'
    ENTITIES = { 'U': 'V', 'P': 'W', 'I': 'A', 'EP': 'kWh', 'EI': 'Ah' }
    AGGREGATED = [ ('P', 'W'), ('E', 'kWh') ]

    def __init__(self, struct={}):
        Config.Base.__init__(self, struct)

        # _status_topic = '{topic_prefix}/{device_name}/{sensor_name}/status'
        # _channel_topic = '{topic_prefix}/{device_name}/{sensor_name}/ch{channel}'

        # _auto_discovery_topic = '{auto_discovery_prefix}/sensor/{device_name}_{sensor_name}_ch{channel}_{entity}/config'
        # _model = 'RPI.ina3221-power-monitor'
        # _manufacturer = 'KFCLabs'
        # _entities = {
        #     'U': 'V',
        #     'P': 'W',
        #     'I': 'A',
        #     'EP': 'kWh',
        #     'EI': 'Ah'
        # }
        # _aggregated = [
        #     ('P', 'W'),
        #     ('E', 'kWh')
        # ]

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

    def get_motion_topic(self, timestamp):
        return self._format_topic(saelf.motion_topic, ts=timestamp)

    def get_auto_discovery_topic(self, channel, entity):
        return self._format_topic(self.AUTO_DISCOVERY_TOPC, channel=channel, entity=entity)


class Calibration(Config.Base, SDL_Pi_INA3221.Calibration):

    vshunt_raw_offset = 0       # raw shunt sensor offset
    vshunt_multiplier = 1.0     # shunt voltage multiplier (effectively current divider)
    vbus_multiplier = 1.0       # vbus voltagte multiplier
    shunt = 100.0               # shunt value in mOhm

    def __init__(self, struct={}):
        Config.Base.__init__(self, struct)
        SDL_Pi_INA3221.Calibration.__init__(self, disabled=True)
        self._multipliers = {}
        self._channel = None
        self._vshunt_raw_offset = None
        self._vshunt_multiplier = None
        self._vbus_multiplier = None
        self._shunt = None

    def _update_multipliers(self):
        self._multipliers.update({
            'mA': SDL_Pi_INA3221.Calibration.RAW_VSHUNT_TO_MILLIVOLT / (self._shunt / (self._vshunt_multiplier * 1000.0)),
            'A': SDL_Pi_INA3221.Calibration.RAW_VSHUNT_TO_MILLIVOLT / (self._shunt / self._vshunt_multiplier),
            'mV': self._vbus_multiplier * SDL_Pi_INA3221.Calibration.RAW_VBUS_TO_VOLT * 0.001,
            'V': self._vbus_multiplier * SDL_Pi_INA3221.Calibration.RAW_VBUS_TO_VOLT
        })

    def __setattr__(self, key, val):
        # print("__setattr__", key, val)

        if key in self.__dir__():
            self.__setattr__('_' + key, val)
            return
        if key in('_channel', '_vshunt_raw_offset', '_multipliers'):
            object.__setattr__(self, key, val)
            return
        if key in('_shunt', '_vshunt_multiplier', '_vbus_multiplier'):
            object.__setattr__(self, key, val)
            if self._channel!=None:
                self._update_multipliers()
            return

        Config.Base.__setattr__(self, key, val)

    def __dir__(self):
        return ['vshunt_raw_offset', 'vshunt_multiplier', 'vbus_multiplier', 'shunt']

    # returns current in mA or A for the given raw shut voltage
    def get_current_from_shunt(self, raw_value, for_unit='mA'):
        # dividing the shunt equals multiplying the voltage
        # V = I * (R / Cvbus) == R = (Cvbus * V) / I
        return self._mul[for_unit] * (raw_value + self._vshunt_raw_offset)

    # unit 'V' or 'mV'
    def get_vbus_voltage(self, raw_value, unit='V'):
        return self._mul[unit] * raw_value

class Channels(list):

    def __init__(self):
        list.__init__([])

#     def __getitem__(self, key):
#         return list.__getitem__(self, key)

#     def __setitem__(self, key, channel):
#         list.__setitem__(self, key, channel)

#     def __dir__(self):
#         return range(0, self.__len__())

#     def __len__(self):
#         return list.__len__(self)


class ChannelCalibration(object):
    def __init__(self):
        pass

    def __getitem__(self, key):
        if key>=0 and key<len(self):
            print(dir(app.channels[key].calibration))
            return app.channels[key].calibration
        raise KeyError('invalid channel: %u' % key)

    def __len__(self):
        return len(app.channels)

#
# Author: sascha_lammers@gmx.de
#

import Config
class app(object):
    pass

class App(Config.Base):

    VERSION = '0.0.1'
    CONFIG_DIR = '.'

    energy_storage_file = '{config_dir}/energy.json'
    config_file = '{config_dir}/config.json'

    headless = False
    verbose = False
    daemon = False

    def __init__(self, struct={}):
        Config.Base.__init__(self, struct)

class ChannelList(Config.ListBase):
    def __init__(self, struct):
        Config.ListBase.__init__(self, struct)

class Channel(Config.ItemBase):

    number = (lambda path: path.index, (Config.Param.ReadOnly,))
    enabled = False
    voltage = (None, (float))

    def __init__(self, struct, index):
        Config.ItemBase.__init__(self, struct, index)

class Calibration(Config.Base):

    vshunt_raw_offset = 0       # raw shunt sensor offset
    vshunt_multiplier = 1.0     # shunt voltage multiplier (effectively current divider)
    vbus_multiplier = 1.0       # vbus voltagte multiplier
    shunt = 100.0               # shunt value in mOhm

    def __init__(self, struct={}):
        Config.Base.__init__(self, struct)

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

    STATUS_TOPC = '{topic_prefix}/{device_name}/{sensor_name}/status'
    CHANNEL_TOPIC = '{topic_prefix}/{device_name}/{sensor_name}/ch{channel}'

    AUTO_DISCOVERY_TOPC = '{auto_discovery_prefix}/sensor/{device_name}_{sensor_name}_ch{channel}_{entity}/config'
    MODEL = 'RPI.ina3221-power-monitor'
    MANUFACTURER = 'KFCLabs'
    ENTITIES = { 'U': 'V', 'P': 'W', 'I': 'A', 'EP': 'kWh', 'EI': 'Ah' }
    AGGREGATED = [ ('P', 'W'), ('E', 'kWh') ]

    def __init__(self, struct={}):
        Config.Base.__init__(self, struct)


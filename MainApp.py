#
# Author: sascha_lammers@gmx.de
#

import tkinter
import tkinter as tk
from tkinter import ttk
import tkinter.messagebox
from os import path
import json
import sys
import math
import matplotlib.animation as animation
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
import numpy
import time
import SDL_Pi_INA3221
import threading
from threading import Lock
import paho.mqtt.client
import glob
import hashlib
import pigpio
import FormatFloat
try:
    import commentjson.commentjson as json
except:
    import json
import re

def appdir_relpath(filename):
    app_dir = path.dirname(path.realpath(__file__))
    return path.realpath(path.join(app_dir, filename))

def get_mac_addresses():
    parts = []
    path = '/sys/class/net/'
    address = '/address'
    # exclude list
    exclude_ifnames = ['lo']
    for iface in glob.glob('%s*%s' % (path, address)):
        ifname = iface[len(path):-len(address)]
        if not ifname in exclude_ifnames:
            try:
                with open(iface, 'r') as f:
                    mac = f.readline().strip()
                    # skip any mac address that consists of zeros only
                    if mac.strip('0:')!='':
                        parts.append(mac)
            except:
                pass
    return parts

class MergeConfig:

    _modified_vars = {}
    _show_defaults = False      # when using check config, display default value if the value has been modified

    def get_default(key, vars=None):
        if vars==None:
            vars = MergeConfig._modified_vars
        if MergeConfig._show_defaults and key in vars:
            return ' (DEFAULT="%s" %s)' % (vars[key], type(vars[key]))
        return ''

    def type_str(val):
        if isinstance(val, str):
            return 'String'
        if isinstance(val, int):
            return 'Integer'
        if isinstance(val, float):
            return 'Float'
        if isinstance(val, bool):
            return 'Boolean'
        if isinstance(val, list):
            return 'List'
        return str(type(val)).split("'")[1]

    def is_valid_key(key):
        return not (key.startswith('_') or key=='n' or key.upper()==key)

    def key_name(sub, key, list_name):
        if sub==None:
            return key
        if list_name:
            return '%s[%s].%s' % (list_name, sub, key)
        return '%s.%s' % (sub, key)

    def merge(config, sub, obj, exception=True, list_name=None):
        if sub!=None:
            config = config[sub]
        if config==None:
            return
        if isinstance(config, list):
            obj = getattr(obj, sub)
            for idx in range(0, len(config)):
                MergeConfig.merge(config, idx, obj[idx], list_name=sub)
            return

        for key, val in config.items():
            if key=='check' or key=='debug':
                continue
            if not MergeConfig.is_valid_key(key):
                raise RuntimeError('Invalid configuration key: %s' % MergeConfig.key_name(sub, key, list_name))
            if val!=None:
                akey = key
                if not hasattr(obj, akey):
                    akey = '%s_%s' % (sub, key)
                    if not hasattr(obj, akey):
                        if exception:
                            raise RuntimeError('Invalid configuration key: %s' % MergeConfig.key_name(sub, key, list_name))
                        return

                attr = getattr(obj, akey)
                if isinstance(attr, float) and isinstance(val, int): # allow int for floats
                    val = float(val)

                if type(attr)!=type(val):
                    raise RuntimeError('Invalid type for configuration key: %s: got %s: excepted %s: value %s' % (MergeConfig.key_name(sub, key, list_name), MergeConfig.type_str(val), MergeConfig.type_str(attr), str(val)))

                if val!=attr:
                    setattr(obj, akey, val)
                    if not akey in obj._modified_vars:
                        obj._modified_vars[akey] = attr

class ChannelConfig:

    def __init__(self, number, name, shunt=100.0, voltage=12.0, enabled=True, calibration=1.0, offset=0, color=None):
        self._modified_vars = {}
        self.number = number
        self.n = number -1
        self.name = name
        self.calibration = calibration
        self.shunt = shunt
        self.color = color
        self.enabled = enabled
        self.voltage = voltage
        self.offset = offset
        self.max_power = None
        self.max_current = None
        self.max_voltage = None
        self.min_voltage = None
        self.warnings = {}

    def add_warning(vtype, value):
        t = time.monotonic()
        if not vtype in self.warnings:
            self.warnings[vtype] = {'min_value': 0, 'max_value': 0, 'time': t }
        self.warnings[vtype]['min_value'] = min(self.warnings[vtype]['min_value'], value)
        self.warnings[vtype]['max_value'] = max(self.warnings[vtype]['max_value'], value)
        diff = t - self.warnings[vtype]['time']
        if diff>AppConfig.repeat_warning_delay:
            pass

    def get_default(self, key):
        return MergeConfig.get_default(key, self._modified_vars)

    def get_shunt_value(self):
        return self.shunt / (self.calibration * 1000)

    def y_ticks(self):
        s = []
        l = []
        for i in range(-20, 21, 10):
            u = self.voltage + (i / 100)
            s.append(u)
            l.append('%.1f' % u)
        return (s, l)

class AppConfig(MergeConfig):

    DISPLAY_ENERGY_AH = 'Ah'
    DISPLAY_ENERGY_WH = 'Wh'

    channels = []

    config_dir = './'
    energy_storage = 'energy.json'
    config_file = 'config.json'

    plot_refresh_interval = 250
    plot_idle_refresh_interval = 2500
    plot_max_values = 200

    plot_main_y_max = 1.05
    plot_main_y_min = 0.5
    plot_main_current_rounding = 0.25
    plot_main_power_rounding = 2.0
    plot_voltage_ymax = 1.005
    plot_voltage_ymin = 0.995

    repeat_warning_delay = 300
    warning_command = ""

    fullscreen = True
    headless = False
    display = '$DISPLAY'
    verbose = False

    backlight_gpio = 0

    def init(dir):
        AppConfig.config_dir = dir
        AppConfig.channels = [
            ChannelConfig(1, 'Channel 1'),
            ChannelConfig(2, 'Channel 2'),
            ChannelConfig(3, 'Channel 3'),
        ]

    def get_config_filename(file=None):
        if file==None:
            file = AppConfig.config_file
        return path.realpath(path.join(AppConfig.config_dir, file))

    _debug = True
    _terminate = False

    # if _debug is set to True, the entire program will be terminated
    def _debug_exception(e):
        if AppConfig._debug:
            if AppConfig._terminate:
                AppConfig._terminate.set()
            raise e

class MqttConfig(MergeConfig):

    VERSION = '0.0.1'

    device_name = 'PowerMonitor'
    sensor_name = 'INA3221'

    host = ''
    port = 1883
    keepalive = 60
    qos = 2

    topic_prefix = 'home'
    auto_discovery = True
    auto_discovery_prefix = 'homeassistant'

    update_interval = 60

    payload_online = 1
    payload_offline = 0

    _status_topic = '{topic_prefix}/{device_name}/{sensor_name}/status'
    _channel_topic = '{topic_prefix}/{device_name}/{sensor_name}/ch{channel}'

    _auto_discovery_topic = '{auto_discovery_prefix}/sensor/{device_name}_{sensor_name}_ch{channel}_{entity}/config'
    _model = 'RPI.ina3221-power-monitor'
    _manufacturer = 'KFCLabs'
    _entities = {
        'U': 'V',
        'P': 'W',
        'I': 'A',
        'EP': 'kWh',
        'EI': 'Ah'
    }
    _aggregated = [
        ('P', 'W'),
        ('E', 'kWh')
    ]

    def init(device_name):
        MqttConfig.device_name = device_name

    def _format_topic(topic, channel='-', entity='-'):
        return topic.format(topic_prefix=MqttConfig.topic_prefix, auto_discovery_prefix=MqttConfig.auto_discovery_prefix, device_name=MqttConfig.device_name, sensor_name=MqttConfig.sensor_name, channel=channel, entity=entity)

    def get_channel_topic(channel):
        return MqttConfig._format_topic(MqttConfig._channel_topic, channel=channel)

    def get_status_topic():
        return MqttConfig._format_topic(MqttConfig._status_topic)

    def get_auto_discovery_topic(channel, entity):
        return MqttConfig._format_topic(MqttConfig._auto_discovery_topic, channel=channel, entity=entity)

class ConfigLoader:

    def load_config(args=None, exit_on_error=False):
        try:
            file = AppConfig.get_config_filename()
            with open(file, 'r') as f:
                config = json.loads(f.read())
                AppConfig.merge(config, 'channels', AppConfig)
                AppConfig.merge(config, 'plot', AppConfig)
                AppConfig.merge(config, 'backlight', AppConfig)
                AppConfig.merge(config, 'logging', AppConfig)
                AppConfig.merge(config, 'app', AppConfig)
                if args:
                    AppConfig.merge(args.__dict__, None, AppConfig)
                MqttConfig.merge(config, 'mqtt', MqttConfig)
        except Exception as e:
            print("Failed to read configuration: %s" % file)
            print(e)
            if exit_on_error:
                sys.exit(-1)

class MainAppCLI(object):

    def __init__(self, logger, *args, **kwargs):

        self.gui = False
        self.fullscreen_state = False
        self.logger = logger

        # sensor

        self.ina3221 = SDL_Pi_INA3221.SDL_Pi_INA3221(addr=0x40, avg=SDL_Pi_INA3221.INA3211_CONFIG.AVG_x128, shunt=1)
        self.lock = Lock()

        # init variables

        self.init_vars()

    def init_vars(self):

        self.channels = AppConfig.channels
        self.channel_num = 0
        for channel in self.channels:
            self.ina3221.setOffset(channel.number, channel.offset)
            if channel.enabled:
                self.channel_num += 1

        self.display_energy = AppConfig.DISPLAY_ENERGY_AH

        self.labels = {
            0: {'U': 0, 'e': 0},
            1: {'U': 0, 'e': 0},
            2: {'U': 0, 'e': 0}
        }

        self.values = {
            0: [[], [], [], []],
            1: [[], [], [], []],
            2: [[], [], [], []]
        }
        self.reset_avg()
        self.load_energy();

        self.reset_data()

        self.lines1 = {}
        self.lines2 = {}

        self.mqtt_connected = False

    def start(self):
        self.start_time = time.monotonic()
        self.terminate = threading.Event()
        AppConfig._terminate = self.terminate

        self.threads = []

        if MqttConfig.host:
            thread = threading.Thread(target=self.update_mqtt, args=(), daemon=True)
            thread.start()
            self.threads.append(thread)
            self.init_mqtt()
        elif AppConfig.headless==True:
            print('MQTT or GUI must be enabled, exiting...')
            sys.exit(-1)

        thread = threading.Thread(target=self.read_sensor, args=(), daemon=True)
        thread.start()
        self.threads.append(thread)

        if AppConfig.backlight_gpio:
            thread = threading.Thread(target=self.backlight_service, args=(), daemon=True)
            thread.start()
            self.threads.append(thread)

    def destroy(self):
        self.end_mqtt()
        self.terminate.set();

    def quit(self):
        self.logger.debug('end')
        sys.exit(0)

    def mainloop(self):
        while not self.terminate.is_set():
            self.logger.debug('ping mainloop')
            self.terminate.wait(60)

        self.logger.debug('waiting for threads to terminate...')
        for thread in self.threads:
            thread.join()
        self.quit()

    def backlight_service(self):

        pi = pigpio.pi()
        while not self.terminate.is_set():
            sleep = 5
            if self.fullscreen_state:
                try:
                    dc = pi.get_PWM_dutycycle(AppConfig.backlight_gpio)
                    if dc<10:
                        self.set_screen_update_rate(False)
                    else:
                        self.set_screen_update_rate(True)
                except Exception as e:
                    self.logger.debug('Failed to get duty cycle for GPIO %u' % AppConfig.backlight_gpio)
                    AppConfig._debug_exception(e)
                    sleep = 60
            self.terminate.wait(sleep)

    def read_sensor(self):
        while not self.terminate.is_set():
            for channel in self.channels:

                t = time.monotonic()
                busvoltage = self.ina3221.getBusVoltage_V(channel.number)
                shuntvoltage = self.ina3221.getShuntVoltage_mV(channel.number)
                current = self.ina3221.getCurrent_mA(channel.number) / channel.get_shunt_value()
                loadvoltage = busvoltage - (shuntvoltage / 1000.0)
                current = current / 1000.0
                power = (current * busvoltage)

                self.lock.acquire()
                try:
                    self.averages[channel.n]['n'] += 1
                    self.averages[channel.n]['U'] += loadvoltage
                    self.averages[channel.n]['I'] += current
                    self.averages[channel.n]['P'] += power

                    if channel.enabled:
                        if self.energy[channel.n]['t']==0:
                            self.energy[channel.n]['t'] = t
                        else:
                            diff = t - self.energy[channel.n]['t']
                            # do not add if there is a gap
                            if diff<1.0:
                                self.energy[channel.n]['ei'] += (diff * current / 3600)
                                self.energy[channel.n]['ep'] += (diff * power / 3600)
                            else:
                                self.logger.error('energy error diff: channel %u: %f' % (channel.n, diff))
                            self.energy[channel.n]['t'] = t

                        self.data.append({'n': channel.n, 't': t, 'I': current, 'U': loadvoltage, 'P': power })

                        if t>self.energy['stored'] + 60:
                            self.energy['stored'] = t;
                            self.store_energy()
                finally:
                    self.lock.release()

            self.terminate.wait(0.1)


    def init_mqtt(self):
        self.client = paho.mqtt.client.Client(clean_session=True)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        if False:
            self.client.on_log = self.on_log
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.will_set(MqttConfig.get_status_topic(), payload=MqttConfig.payload_offline, qos=MqttConfig.qos, retain=True)
        self.logger.debug("MQTT connect: %s:%u" % (MqttConfig.host, MqttConfig.port))
        self.client.connect(MqttConfig.host, port=MqttConfig.port, keepalive=MqttConfig.keepalive)
        self.client.loop_start();

    def end_mqtt(self):
        if self.mqtt_connected:
            self.client.disconnect(True)
            self.mqtt_connected = False

    def create_hass_auto_conf(self, entity, channel, unit, value_json_name, mac_addresses):

        m = hashlib.md5()
        m.update((':'.join([MqttConfig.device_name, MqttConfig._model, MqttConfig._manufacturer, str(channel), entity, value_json_name])).encode())
        unique_id = m.digest().hex()[0:11]

        m = hashlib.md5()
        m.update((':'.join([MqttConfig.device_name, MqttConfig._model, MqttConfig._manufacturer, entity, value_json_name])).encode())
        device_unique_id = m.digest().hex()[0:11]

        connections = []
        for mac_addr in mac_addresses:
            connections.append(["mac", mac_addr])

        return json.dumps({
            'name': '%s-%s-ch%u-%s' % (MqttConfig.device_name, MqttConfig.sensor_name, channel, entity),
            'platform': 'mqtt',
            'unique_id': unique_id,
            'device': {
                'name': '%s-%s-%s' % (MqttConfig.device_name, MqttConfig.sensor_name, device_unique_id[0:4]),
                'identifiers': [ device_unique_id, '947bc81af46aa573a62ccefadb9c9a7aef6d1c1e' ],
                'connections': connections,
                'model': MqttConfig._model,
                'sw_version': MqttConfig.VERSION,
                'manufacturer': MqttConfig._manufacturer
            },
            'availability_topic': MqttConfig.get_status_topic(),
            'payload_available': MqttConfig.payload_online,
            'payload_not_available': MqttConfig.payload_offline,
            'state_topic': MqttConfig.get_channel_topic(channel),
            'unit_of_measurement': unit,
            'value_template': '{{ value_json.%s }}' % value_json_name
        }, ensure_ascii=False, indent=None, separators=(',', ':'))


    def mqtt_publish_auto_discovery(self):
        mac_addresses = get_mac_addresses()

        for entity, unit in MqttConfig._aggregated:
            payload = self.create_hass_auto_conf(entity, 0, unit, entity, mac_addresses)
            topic = MqttConfig.get_auto_discovery_topic(0, entity)
            self.logger.debug('MQTT auto discovery %s: %s' % (topic, payload))
            self.client.publish(topic, payload=payload, qos=MqttConfig.qos, retain=True)

        for channel in self.channels:
            for entity, unit in MqttConfig._entities.items():
                payload = self.create_hass_auto_conf(entity, channel.number, unit, entity, mac_addresses)
                topic = MqttConfig.get_auto_discovery_topic(channel.number, entity)
                self.logger.debug('MQTT auto discovery %s: %s' % (topic, payload))
                self.client.publish(topic, payload=payload, qos=MqttConfig.qos, retain=True)

    def on_log(self, client, userdata, level, buf):
        self.logger.debug('%s: %s' % (level, buf))

    def on_connect(self, client, userdata, flags, rc):
        self.logger.debug("MQTT on_connect: %u" % rc)
        self.mqtt_connected = False
        if rc==0:
            try:
                self.mqtt_connected = True
                self.client.publish(MqttConfig.get_status_topic(), MqttConfig.payload_online, qos=MqttConfig.qos, retain=True)
                if MqttConfig.auto_discovery:
                    self.mqtt_publish_auto_discovery()
            except Exception as e:
                self.logger.error('MQTT error: %s: reconnecting...' % e)
                AppConfig._debug_exception(e)
                self.client.reconnect()

    def on_disconnect(self, client, userdata, rc):
        self.logger.debug("MQTT on_disconnect: %u" % rc)
        self.mqtt_connected = False

    def format_float_precision(self, value, limits = [(1.0, 4), (10.0, 3), (100.0, 2), (1000.0, 1), (None, 0)], fmt='%%.%uf'):
        if value == 0:
            return '0.0'
        for max_value, digits in limits:
            if max_value==None or value<max_value:
                fmt = fmt % digits
                result = fmt % value
                if result.strip('0.')=='':
                    return '0.0'
                tmp = result.rstrip('0')
                return tmp.endswith('.') and result or tmp
        raise ValueError('limits limits: None missing: %s' % limits)

    def update_mqtt(self):

        # wait 5 seconds for the initial connection to be established
        self.terminate.wait(5)

        while not self.terminate.is_set():
            if self.mqtt_connected:
                tmp = None
                self.lock.acquire()
                try:
                    tmp = self.averages.copy()
                    tmp2 = self.energy.copy()
                    self.reset_avg()
                finally:
                    self.lock.release()

                kwh_precision = [(.001, 6), (.01, 5), (.1, 4), (1.0, 3), (100.0, 2), (None, 0)]

                try:
                    sum_data = {
                        'E': 0,
                        'P': 0
                    }

                    for n, avg in tmp.items():
                        if avg['n']:
                            I = avg['I'] / avg['n']
                            P = avg['P'] / avg['n']
                            U = avg['U'] / avg['n']

                            payload = json.dumps({
                                'U': self.format_float_precision(U),
                                'P': self.format_float_precision(P),
                                'I': self.format_float_precision(I),
                                'EI': self.format_float_precision(tmp2[n]['ei']),
                                'EP': self.format_float_precision(tmp2[n]['ep'] / 1000, kwh_precision), # ep is Wh, we send kWh
                            })

                            sum_data['E'] += tmp2[n]['ep']
                            sum_data['P'] += P

                            topic = MqttConfig.get_channel_topic(n + 1)
                            self.logger.debug("MQTT publish %s: %s" % (topic, payload))
                            self.client.publish(topic, payload=payload, qos=MqttConfig.qos, retain=True)


                    payload = json.dumps({
                        'P': self.format_float_precision(sum_data['P']),
                        'E': self.format_float_precision(sum_data['E'] / 1000, kwh_precision),  # E is Wh, we send kWh
                    })
                    topic = MqttConfig.get_channel_topic(0)
                    self.logger.debug("MQTT publish %s: %s" % (topic, payload))
                    self.client.publish(topic, payload=payload, qos=MqttConfig.qos, retain=True)

                except Exception as e:
                    self.logger.error('MQTT error: %s: reconnecting...' % e)
                    AppConfig._debug_exception(e)
                    self.client.reconnect()

            self.terminate.wait(MqttConfig.update_interval)

    def reset_data(self):
        self.data = []

    def reset_avg(self):
        self.averages = {
            0: {'n':0, 'I': 0, 'U': 0, 'P': 0},
            1: {'n':0, 'I': 0, 'U': 0, 'P': 0},
            2: {'n':0, 'I': 0, 'U': 0, 'P': 0}
        }

    def reset_energy(self):
        self.energy = {
            0: {'t': 0, 'ei': 0, 'ep': 0},
            1: {'t': 0, 'ei': 0, 'ep': 0},
            2: {'t': 0, 'ei': 0, 'ep': 0},
            'stored': 0,
        }

    def load_energy(self):
        try:

            with open(AppConfig.get_config_filename(AppConfig.energy_storage), 'r') as f:
                tmp = json.loads(f.read())
                self.reset_energy()
                for channel in self.channels:
                    nstr = str(channel.n)
                    self.energy[channel.n]['ei'] = float(tmp[nstr]['ei']);
                    self.energy[channel.n]['ep'] = float(tmp[nstr]['ep']);
        except Exception as e:
            self.logger.error("failed to load energy: %s" % e)
            self.reset_energy()

    def store_energy(self):
        try:
            with open(AppConfig.get_config_filename(AppConfig.energy_storage), 'w') as f:
                tmp = self.energy.copy()
                for channel in self.channels:
                    tmp[channel.n]['t'] = 0;
                f.write(json.dumps(tmp))
        except Exception as e:
            self.logger.error("failed to store energy: %s" % e)

class MainApp(MainAppCLI, tk.Tk):

    MAIN_PLOT_CURRENT = 'current'
    MAIN_PLOT_POWER = 'power'
    MAIN_PLOT_POWER_SUM = 'power_sum'

    def __init__(self, logger):

        MainAppCLI.__init__(self, logger)

        if AppConfig.headless:
            self.logger.debug('starting headless')
            return

        try:
            self.__init_gui__()
        except Exception as e:
            self.logger.error("failed to initialize GUI: %s" % e)
            self.logger.debug('starting headless')
            AppConfig._debug_exception(e)

    def __init_gui__(self):

        self.logger.debug('starting with GUI')

        tk.Tk.__init__(self)
        tk.Tk.wm_title(self, "Power Monitor")

        self.gui = True

        # set to false for OLED
        self.desktop = True
        self.color_schema_dark = True
        self.monochrome = False

        # color scheme and screen size
        self.init_scheme()

        # init TK

        self.configure(bg=self.BG_COLOR)

        top = tk.Frame(self)
        top.pack(side=tkinter.TOP)
        top.place(relwidth=1.0, relheight=1.0)

        # plot

        self.fig = Figure(figsize=(3, 3), dpi=self.PLOT_DPI, tight_layout=True, facecolor=self.BG_COLOR)

        # axis

        self.ax = []
        ax = self.fig.add_subplot(121, facecolor=self.PLOT_BG)
        self.ax.append(ax)

        number = 1
        for channel in self.channels:
            if channel.enabled:
                n = (self.channel_num * 100) + 20 + (number * 2)
                number += 1
                self.ax.append(self.fig.add_subplot(n, facecolor=self.PLOT_BG))
            else:
                self.ax.append(None)

        for ax in self.ax:
            if ax:
                ax.grid(True, color=self.PLOT_GRID)
                ax.set_xticks([])
                ax.set_xticklabels([])

        ticks_params = {
            'labelcolor': self.PLOT_TEXT,
            'axis': 'y',
            'labelsize': self.PLOT_FONT['fontsize'] - 1,
            'width': 0,
            'length': 0,
            'pad': 1
        }

        self.ax[0].set_ylabel('Current (A)', color=self.PLOT_TEXT, **self.PLOT_FONT)
        self.ax[0].tick_params(**ticks_params)

        for channel in self.channels:
            if channel.enabled:
                ax = self.ax[channel.number]
                ax.ticklabel_format(axis='y', style='plain', scilimits=(0, 0), useOffset=False)
                ax.tick_params(**ticks_params)

        # lines

        self.main_plot_index = 4
        self.set_main_plot(self.MAIN_PLOT_CURRENT)

        for channel in self.channels:
            if channel.enabled:
                line, = self.ax[channel.number].plot(self.values[channel.n][0], self.values[channel.n][2], channel.color, label=channel.name, linewidth=2)
                self.lines2[channel.n] = line

        # top labels

        label_font_size = [32, 28, 18]
        label_config = {
            'font': (self.TOP_FONT, label_font_size[self.channel_num - 1]),
            'bg': self.BG_COLOR,
            'fg': 'white',
            'anchor': 'center'
        }

        # top frame for enabled channels
        # 1 colum per active channel
        top_frame = {
            1: { 'relx': 0.0, 'rely': 0.0, 'relwidth': 1.0, 'relheight': 0.12 },
            2: { 'relx': 0.0, 'rely': 0.0, 'relwidth': 0.5, 'relheight': 0.17 },
            3: { 'relx': 0.0, 'rely': 0.0, 'relwidth': 0.33, 'relheight': 0.17 }
        }

        # add plot to frame before labels for the z order

        self.canvas = FigureCanvasTkAgg(self.fig, self)
        self.canvas.draw()
        # self.canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=0, padx=0)
        self.canvas.get_tk_widget().pack()

        gui = {}
        try:
            with open(AppConfig.get_config_filename(self.get_gui_config_filename()), 'r') as f:
                gui = json.loads(f.read())
        except Exception as e:
            self.logger.debug('failed to write GUI config: %s' % e)
            gui = {}

        gui['geometry'] = self.geometry_info

        padding_y = { 1: 100, 2: 70, 3: 70 }
        pady = -1 / padding_y[self.channel_num]
        padx = -1 / 50
        y = top_frame[self.channel_num]['relheight'] + pady
        if 'plot_placement' in gui:
            plot_placement = gui['plot_placement']
        else:
            plot_placement = {
                'relwidth': 1.0-padx,
                'relheight': 1-y-pady*2,
                'rely': y,
                'relx': padx
            }
            gui['plot_placement'] = plot_placement

        self.canvas.get_tk_widget().place(in_=top, **plot_placement)
        self.ani = animation.FuncAnimation(self.fig, self.plot_values, interval=AppConfig.plot_refresh_interval)

        # label placement for the enabled channels
        if 'label_places' in gui:
            places = gui['label_places'].copy()
        else:
            places = []
            pad = 1 / 200
            pad2 = pad * 2
            if self.channel_num==1:
                # 1 row 4 cols
                w = 1 / 4
                h = 1.0
                for i in range(0, 4):
                    x = i / 4
                    places.append({'relx': x + pad, 'rely': pad, 'relwidth': w - pad2, 'relheight': h - pad2})
            elif self.channel_num==2:
                # 2x 2 row 2 cols
                w = 1 / 2
                h = 1 / 2
                for i in range(0, 8):
                    x = (i % 2) / 2
                    y = (int(i / 2) % 2) * h
                    places.append({'relx': x + pad, 'rely': y + pad, 'relwidth': w - pad2, 'relheight': h - pad2})
            elif self.channel_num==3:
                # 3x 2 row 2 cols
                w = 1 / 3
                h = 1 / 2
                for i in range(0, 12):
                    x = (i % 2) / 3
                    y = (int(i / 2) % 2) * h
                    places.append({'relx': x + pad, 'rely': y + pad, 'relwidth': w - pad2, 'relheight': h - pad2})
            gui['label_places'] = places.copy()

        for channel in self.channels:
            if channel.enabled:
                label_config['fg'] = channel.color

                frame = tk.Frame(self, bg=self.BG_COLOR)
                frame.pack()
                frame.place(in_=top, **top_frame[self.channel_num])
                top_frame[self.channel_num]['relx'] += top_frame[self.channel_num]['relwidth']

                label = tk.Label(self, text="- V", **label_config)
                label.pack(in_=frame)
                label.place(in_=frame, **places.pop(0))
                self.labels[channel.n]['U'] = label

                label = tk.Label(self, text="- A", **label_config)
                label.pack(in_=frame)
                label.place(in_=frame, **places.pop(0))
                self.labels[channel.n]['I'] = label

                label = tk.Label(self, text="- W", **label_config)
                label.pack()
                label.place(in_=frame, **places.pop(0))
                self.labels[channel.n]['P'] = label

                label = tk.Label(self, text="- Wh", **label_config)
                label.pack()
                label.place(in_=frame, **places.pop(0))
                self.labels[channel.n]['e'] = label

        try:
            with open(AppConfig.get_config_filename(self.get_gui_config_filename(True)), 'w') as f:
                f.write(json.dumps(gui, indent=2))
        except Exception as e:
            self.logger.debug('failed to write GUI config: %s' % e)

        if AppConfig.fullscreen:
            self.attributes('-zoomed', True)
            self.toggle_fullscreen()
            self.bind("<F3>", self.toggle_main_plot)
            self.bind("<F4>", self.toggle_display_energy)
            self.bind("<F8>", self.reload_gui)
            self.bind("<F9>", self.reload_config)
            self.bind("<F11>", self.toggle_fullscreen)
            self.bind("<Escape>", self.end_fullscreen)

        self.start()

    def start(self):
        MainAppCLI.start(self)

    def destroy(self):
        MainAppCLI.destroy(self)
        if self.gui:
            tk.Tk.destroy(self)

    def mainloop(self):
        self.logger.debug('mainloop gui=%s' % self.gui)
        if self.gui:
            tk.Tk.mainloop(self)
        else:
            MainAppCLI.mainloop(self)

    def quit(self):
        if self.gui:
            tk.Tk.quit(self)
        MainAppCLI.quit(self)

    def init_scheme(self):
        if not self.desktop:
            self.geometry_info = (128, 64, 2.0)
        else:
            self.geometry_info = (800, 480, 1.0)

        self.geometry("%ux%u" % (self.geometry_info[0], self.geometry_info[1]))
        self.tk.call('tk', 'scaling', self.geometry_info[2])

        if self.color_schema_dark:
            self.BG_COLOR = 'black'
            self.TEXT_COLOR = 'white'
            self.PLOT_TEXT = self.TEXT_COLOR
            self.PLOT_GRID = 'gray'
            self.PLOT_BG = "#303030"
        else:
            self.BG_COLOR = 'white'
            self.TEXT_COLOR = 'black'
            self.PLOT_TEXT = self.TEXT_COLOR
            self.PLOT_GRID = 'black'
            self.PLOT_BG = "#f0f0f0"

        if self.monochrome:
            self.FG_CHANNEL1 = 'white'
            self.FG_CHANNEL2 = 'white'
            self.FG_CHANNEL3 = 'white'
        else:
            if self.color_schema_dark:
                self.FG_CHANNEL1 = 'lime'
                self.FG_CHANNEL2 = 'deepskyblue'
                self.FG_CHANNEL3 = '#b4b0d1' # 'lavender'
            else:
                self.FG_CHANNEL1 = 'green'
                self.FG_CHANNEL2 = 'blue'
                self.FG_CHANNEL3 = 'aqua'

        self.channels[0].color = self.FG_CHANNEL1
        self.channels[1].color = self.FG_CHANNEL2
        self.channels[2].color = self.FG_CHANNEL3

        if self.desktop:
            self.TOP_FONT = "DejaVu Sans"
            self.PLOT_FONT = {'fontname': 'DejaVu Sans', 'fontsize': 9}
            self.TOP_PADDING = (2, 20)
            self.PLOT_DPI = 200
            self.LABELS_PADX = 10
        else:
            self.TOP_FONT = "Small Pixel7"
            self.PLOT_FONT = {'fontname': 'Small Pixel7'}
            self.TOP_PADDING = (0, 1)
            self.PLOT_DPI = 43
            self.LABELS_PADX = 1


    def set_screen_update_rate(self, fast=True):
        if fast:
            rate = AppConfig.plot_refresh_interval
        else:
            rate = AppConfig.plot_idle_refresh_interval
        if rate!=self.ani.event_source.interval:
            self.logger.debug('changing update rate %u' % rate)
            self.ani.event_source.interval = rate

    def get_gui_config_filename(self, auto=''):
        if auto==True:
            auto = '-auto'
        return 'gui-%u-%ux%u%s.json' % (self.channel_num, self.geometry_info[0], self.geometry_info[1], auto)

    def reload_gui(self, event=None):
        try:
            with open(AppConfig.get_config_filename(self.get_gui_config_filename()), 'r') as f:
                gui = json.loads(f.read())

            self.canvas.get_tk_widget().place(**gui['plot_placement'])

            places = gui['label_places']
            for channel in self.channels:
                if channel.enabled:
                    self.labels[channel.n]['U'].place(**places.pop(0))
                    self.labels[channel.n]['I'].place(**places.pop(0))
                    self.labels[channel.n]['P'].place(**places.pop(0))
                    self.labels[channel.n]['e'].place(**places.pop(0))

        except Exception as e:
            self.logger.error('Reloading GUI failed: %s' % e)
        return "break"

    def reload_config(self, event=None):
        try:
            ConfigLoader.load_config()
        except Exception as e:
            self.logger.error('Reloading configuration failed: %s' % e)
        return "break"

    def toggle_fullscreen(self, event=None):
        self.fullscreen_state = not self.fullscreen_state
        self.attributes("-fullscreen", self.fullscreen_state)
        if self.fullscreen_state:
            self.config(cursor='none')
        else:
            self.config(cursor='')
        self.set_screen_update_rate(self.fullscreen_state)
        return "break"

    def end_fullscreen(self, event=None):
        self.fullscreen_state = False
        self.attributes("-fullscreen", False)
        self.config(cursor='')
        self.set_screen_update_rate(False)
        return "break"

    def toggle_main_plot(self, event=None):
        if self.main_plot_index==1:
            self.set_main_plot(self.MAIN_PLOT_POWER)
        elif self.main_plot_index==3:
            self.set_main_plot(self.MAIN_PLOT_POWER_SUM)
        elif self.main_plot_index==4:
            self.set_main_plot(self.MAIN_PLOT_CURRENT)
        return 'break'

    def toggle_display_energy(self, event=None):
        if self.display_energy==AppConfig.DISPLAY_ENERGY_AH:
            self.display_energy=AppConfig.DISPLAY_ENERGY_WH
        else:
            self.display_energy=AppConfig.DISPLAY_ENERGY_AH
        return 'break'

    def set_main_plot(self, type):
        if not self.lock.acquire(True):
            return
        try:
            if type==self.MAIN_PLOT_CURRENT:
                self.main_plot_index = 1
                self.main_plot_y_limit_rounding = AppConfig.plot_main_current_rounding
                self.ax[0].set_ylabel('Current (A)', color=self.PLOT_TEXT, **self.PLOT_FONT)
            elif type==self.MAIN_PLOT_POWER:
                self.main_plot_index = 3
                self.main_plot_y_limit_rounding = AppConfig.plot_main_current_rounding
                self.ax[0].set_ylabel('Power (W)', color=self.PLOT_TEXT, **self.PLOT_FONT)
            elif type==self.MAIN_PLOT_POWER_SUM:
                self.main_plot_index = 4
                self.main_plot_y_limit_rounding = AppConfig.plot_main_power_rounding
                self.ax[0].set_ylabel('Aggregated Power (W)', color=self.PLOT_TEXT, **self.PLOT_FONT)

            for line in self.ax[0].get_lines():
                line.remove()

            if self.main_plot_index==4:
                line, = self.ax[0].plot([1], [1], 'red', label='Power', linewidth=2)
                self.lines1 = line
            else:
                self.lines1 = {}
                for channel in self.channels:
                    if channel.enabled:
                        line, = self.ax[0].plot(self.values[channel.n][0], self.values[channel.n][1], color=channel.color, label=channel.name, linewidth=2)
                        self.lines1[channel.n] = line

        finally:
            self.lock.release()

    def plot_values(self, i):

        try:
            num_values = AppConfig.plot_max_values

            tmp = []
            if not self.lock.acquire(True, 0.1):
                return
            try:
                tmp = self.data.copy();
                tmp2 = self.averages.copy()
                self.reset_data()
            finally:
                self.lock.release()

            for data in tmp:
                n = data['n']
                self.values[n][0].append(data['t'] - self.start_time)
                self.values[n][1].append(data['I'])
                self.values[n][2].append(data['U'])
                self.values[n][3].append(data['P'])

                while len(self.values[n][0])>num_values:
                    self.values[n][0].pop(0)
                    self.values[n][1].pop(0)
                    self.values[n][2].pop(0)
                    self.values[n][3].pop(0)

            fmt = FormatFloat.FormatFloat(4, 5, prefix=FormatFloat.PREFIX.M, strip=FormatFloat.STRIP.NONE)
            fmt.set_precision('m', 1)

            power_sum = []
            y_max = 0
            y_min = 100000
            for channel in self.channels:
                if channel.enabled:
                    n = len(self.values[channel.n][1])
                    if n:
                        x_range = numpy.arange(-n, 0)

                        self.labels[channel.n]['U'].configure(text=fmt.format(numpy.average(self.values[channel.n][2][-10:]), 'V'))
                        self.labels[channel.n]['P'].configure(text=fmt.format(numpy.average(self.values[channel.n][3][-10:]), 'W'))
                        self.labels[channel.n]['I'].configure(text=fmt.format(numpy.average(self.values[channel.n][1][-10:]), 'A'))
                        if self.display_energy==AppConfig.DISPLAY_ENERGY_AH:
                            self.labels[channel.n]['e'].configure(text=fmt.format(self.energy[channel.n]['ei'], 'Ah'))
                        else:
                            self.labels[channel.n]['e'].configure(text=fmt.format(self.energy[channel.n]['ep'], 'Wh'))

                        if self.main_plot_index==4:
                            power_sum.append(self.values[channel.n][3])
                        else:
                            # max. for all lines
                            y_max = max(y_max, max(self.values[channel.n][self.main_plot_index]))
                            y_min = min(y_min, min(self.values[channel.n][self.main_plot_index]))
                            self.lines1[channel.n].set_data(x_range, self.values[channel.n][self.main_plot_index])

                        self.lines2[channel.n].set_data(x_range, self.values[channel.n][2])

                        # max. per channel
                        a = max(max(self.values[channel.n][2]) * AppConfig.plot_voltage_ymax, channel.voltage + 0.01)
                        b = min(min(self.values[channel.n][2]) * AppConfig.plot_voltage_ymin, channel.voltage - 0.01)
                        self.ax[channel.number].set_ylim(top=a, bottom=b)
                        self.ax[channel.number].set_xlim(left=-num_values, right=0)

            if self.main_plot_index==4:
                power_sum = [sum(x) for x in zip(*power_sum)]
                y_max = max(power_sum)
                self.lines1.set_data(x_range, power_sum);

            if y_min==100000:
                y_min=0
            if y_max:
                y_max = int(y_max * AppConfig.plot_main_y_max / self.main_plot_y_limit_rounding + 1) * self.main_plot_y_limit_rounding
                y_min = max(0, int(y_min * AppConfig.plot_main_y_min / self.main_plot_y_limit_rounding - 0.51) * self.main_plot_y_limit_rounding)

                # print(y_max)
                self.ax[0].set_ylim(top=y_max, bottom=y_min)

            self.ax[0].set_xlim(left=-num_values, right=0)

            # for ax in self.ax:
            #     ax.autoscale_view()
            #     ax.relim()

        except Exception as e:
            AppConfig._debug_exception(e)

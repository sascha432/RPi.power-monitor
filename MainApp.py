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
import socket
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

class MqttConfig:
    VERSION = '0.0.1'
    device_name = '%s' % socket.gethostname()
    sensor_name = 'INA3221'

    host = '192.168.0.3'
    port = 1883
    keepalive = 60
    qos = 2

    auto_discovery = True
    auto_discovery_prefix = 'homeassistant'

    update_interval = 15

    payload_online = 1
    payload_offline = 0

    _status_topic = 'home/{device_name}/{sensor_name}/status'
    _channel_topic = 'home/{device_name}/{sensor_name}/ch{channel}'

    _auto_discovery_topic = '{auto_discovery_prefix}/sensor/{device_name}_{sensor_name}_ch{channel}_{entity}/config'
    _model = 'RPI.ina3221-power-monitor'
    _manufacturer = 'KFCLabs'
    _entities = {
        'U': 'V',
        'P': 'W',
        'I': 'mA',
        'EP': 'Wh',
        'EI': 'Ah'
    }

    def _format_topic(topic, channel='-', entity='-'):
        return topic.format(auto_discovery_prefix=MqttConfig.auto_discovery_prefix, device_name=MqttConfig.device_name, sensor_name=MqttConfig.sensor_name, channel=channel, entity=entity)

    def get_channel_topic(channel):
        return MqttConfig._format_topic(MqttConfig._channel_topic, channel=channel)

    def get_status_topic():
        return MqttConfig._format_topic(MqttConfig._status_topic)

    def get_auto_discovery_topic(channel, entity):
        return MqttConfig._format_topic(MqttConfig._auto_discovery_topic, channel=channel, entity=entity)


class ChannelConfig:
    def __init__(self, number, name, color, shunt, voltage, calibration = 1.0, enabled=True):
        self.number = number
        self.n = number -1
        self.name = name
        self.shunt = shunt / calibration
        self.color = color
        self.enabled = enabled
        self.voltage = voltage

    def y_ticks(self):
        s = []
        l = []
        for i in range(-20, 21, 10):
            u = self.voltage + (i / 100)
            s.append(u)
            l.append('%.1f' % u)
        return (s, l)


class MainAppCLI(object):

    def __init__(self, logger, *args, **kwargs):

        self.gui = False
        self.logger = logger

        # sensor

        self.ina3221 = SDL_Pi_INA3221.SDL_Pi_INA3221(addr=0x40, avg=SDL_Pi_INA3221.INA3211_CONFIG.AVG_x128, shunt=1)
        self.ina3221.setOffset(1, -16)
        self.ina3221.setOffset(2, -32)
        self.lock = Lock()

        # backlight monitor

        self.backlight_pi = pigpio.pi()
        self.backlight_gpio = 18

        # init variables

        self.init_vars()

    def init_vars(self):

        self.storage = {
            'dir': '/home/pi/.power_monitor',
            'energy': 'energy.json'
        }

        self.channels = [
            ChannelConfig(1, 'Channel 1 (5V)', 0, 0.020, 5.3, 0.994137858),
            ChannelConfig(2, 'Channel 2 (12V)', 0, 0.025, 12, 0.985870772),
            ChannelConfig(3, 'Channel 3 (24V)', 0, 0.05, 24, enabled=False),
        ]
        self.channel_num = 0
        for channel in self.channels:
            if channel.enabled:
                self.channel_num += 1

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

        self.threads = []

        thread = threading.Thread(target=self.read_sensor, args=(), daemon=True)
        thread.start()
        self.threads.append(thread)

        thread = threading.Thread(target=self.update_mqtt, args=(), daemon=True)
        thread.start()
        self.threads.append(thread)

        if self.backlight_pi:
            thread = threading.Thread(target=self.backlight_service, args=(), daemon=True)
            thread.start()
            self.threads.append(thread)

        self.init_mqtt()

    def destroy(self):
        self.end_mqtt()
        self.terminate.set();

    def quit(self):
        self.logger.debug('end')
        sys.exit(0)

    def mainloop(self):
        self.logger.debug('starting headless')
        while not self.terminate.is_set():
            self.logger.debug('ping mainloop')
            self.terminate.wait(60)

        self.logger.debug('waiting for threads to terminate...')
        for thread in self.threads:
            thread.join()
        self.quit()

    def backlight_service(self):
        while not self.terminate.is_set():
            sleep = 5
            if self.fullscreen_state:
                try:
                    dc = self.backlight_pi.get_PWM_dutycycle(self.backlight_gpio)
                    if dc<10:
                        self.set_screen_update_rate(False)
                    else:
                        self.set_screen_update_rate(True)
                except Exception as e:
                    self.logger.debug('Failed to get duty cycle for GPIO %u' % self.backlight_gpio)
                    sleep = 60
            self.terminate.wait(sleep)

    def read_sensor(self):
        while not self.terminate.is_set():
            for channel in self.channels:

                t = time.monotonic()
                busvoltage = self.ina3221.getBusVoltage_V(channel.number)
                shuntvoltage = self.ina3221.getShuntVoltage_mV(channel.number)
                current = self.ina3221.getCurrent_mA(channel.number) / channel.shunt
                loadvoltage = busvoltage - (shuntvoltage / 1000)
                power = (current * busvoltage) / 1000

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
                                print('energy error diff: channel %u: %f' % (channel.n, diff))
                            self.energy[channel.n]['t'] = t

                        self.data.append({'n': channel.n, 't': t, 'I': current, 'U': loadvoltage, 'P': power })

                        if t>self.energy['stored'] + 60:
                            self.energy['stored'] = t;
                            self.store_energy()
                finally:
                    self.lock.release()

            self.terminate.wait(0.1)


    def format(self, value, digits, unit):
        bfmt = '%%.%uf%%s%%s'
        fmt = bfmt % digits
        md = pow(10, digits)
        if value>=md:
            return fmt % (value / 1000, 'k', unit)
        a = value * 1000
        if a<md:
            fmt = bfmt % (digits - 2)
            return fmt % (a, 'm', unit)
        return fmt % (value, '', unit)

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
            self.mqtt_connected = True
            self.client.publish(MqttConfig.get_status_topic(), MqttConfig.payload_online, qos=MqttConfig.qos, retain=True)
            if MqttConfig.auto_discovery:
                self.mqtt_publish_auto_discovery()

    def on_disconnect(self, client, userdata, rc):
        self.logger.debug("MQTT on_disconnect: %u" % rc)
        self.mqtt_connected = False

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

                for n, avg in tmp.items():
                    if avg['n']:
                        I = avg['I'] / avg['n']
                        P = avg['P'] / avg['n']
                        U = avg['U'] / avg['n']

                        payload = json.dumps({
                            'U': '%.3f' % U,
                            'P': '%.3f' % P,
                            'I': '%.1f' % I,
                            'EI': '%.3f' % (tmp2[n]['ei'] / 1000),
                            'EP': '%.3f' % tmp2[n]['ep'],
                        })

                        topic = MqttConfig.get_channel_topic(n + 1)
                        self.logger.debug("MQTT publish %s: %s" % (topic, payload))
                        self.client.publish(topic, payload=payload, qos=MqttConfig.qos, retain=True)

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
            with open(path.join(self.storage['dir'], self.storage['energy']), 'r') as f:
                tmp = json.loads(f.read())
                self.reset_energy()
                for channel in self.channels:
                    nstr = str(channel.n)
                    self.energy[channel.n]['ei'] = float(tmp[nstr]['ei']);
                    self.energy[channel.n]['ep'] = float(tmp[nstr]['ep']);
        except Exception as e:
            print("failed to load energy: %s" % e)
            self.reset_energy()

    def store_energy(self):
        try:
            with open(path.join(self.storage['dir'], self.storage['energy']), 'w') as f:
                tmp = self.energy.copy()
                for channel in self.channels:
                    tmp[channel.n]['t'] = 0;
                f.write(json.dumps(tmp))
        except Exception as e:
            print(e)
            print("failed to store energy: %s" % e)

class MainApp(MainAppCLI, tk.Tk):

    def __init__(self, logger, init_gui = True):

        MainAppCLI.__init__(self, logger)

        if not init_gui:
            return

        self.__init_gui__()

    def __init_gui__(self):

        self.logger.debug('starting with GUI')

        tk.Tk.__init__(self)
        tk.Tk.wm_title(self, "Power Monitor")

        self.gui = True

        # set to false for OLED
        self.desktop = True
        self.color_schema_dark = True
        self.monochrome = False

        self.update_speed = [200, 5000]

        # color scheme and screen size
        self.init_scheme()

        # init TK

        self.configure(bg=self.BG_COLOR)

        top = tk.Frame(self)
        top.pack(side=tkinter.TOP, pady=0)

        # plot

        self.fig = Figure(figsize=(3, 3), dpi=self.PLOT_DPI, tight_layout=True, facecolor=self.BG_COLOR)

        # axis

        self.ax = []
        ax = self.fig.add_subplot(121, facecolor=self.PLOT_BG)
        self.ax.append(ax)

        for channel in self.channels:
            if channel.enabled:
                n = (self.channel_num * 100) + 20 + (channel.number * 2)
                self.ax.append(self.fig.add_subplot(n, facecolor=self.PLOT_BG))

        for ax in self.ax:
            ax.tick_params(labelcolor=self.PLOT_TEXT)
            ax.grid(True, color=self.PLOT_GRID)
            ax.set_xticks([])
            ax.set_xticklabels([])

        self.ax[0].set_ylabel('Current (mA)', color=self.PLOT_TEXT, **self.PLOT_FONT)
        self.ax[0].tick_params(axis='y', labelsize=self.PLOT_FONT['fontsize'] - 1)

        for channel in self.channels:
            if channel.enabled:
                ax = self.ax[channel.number]
                # ax.set_ylabel('Voltage', color=self.PLOT_TEXT)
                # (ticks, labels) = channel.y_ticks()
                # ax.set_yticks(ticks)
                # ax.set_yticklabels(labels)
                ax.ticklabel_format(axis='y', style='plain', scilimits=(0, 0), useOffset=False)
                ax.tick_params(axis='y', labelsize=self.PLOT_FONT['fontsize'] - 1)

        # lines

        for channel in self.channels:
            if channel.enabled:
                line, = self.ax[0].plot(self.values[channel.n][0], self.values[channel.n][1], channel.color, label=channel.name, linewidth=2)
                self.lines1[channel.n] = line
                line, = self.ax[channel.number].plot(self.values[channel.n][0], self.values[channel.n][2], channel.color, label=channel.name, linewidth=2)
                self.lines2[channel.n] = line

        # add plot to frame

        self.canvas = FigureCanvasTkAgg(self.fig, self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=0, padx=0)
        self.ani = animation.FuncAnimation(self.fig, self.plot_values, interval=self.update_speed[1])

        # labels

        for channel in self.channels:
            if channel.enabled:
                frame = tk.Frame(self, bg=self.BG_COLOR)
                frame.pack(in_=top, side=tkinter.LEFT, padx=0, pady=0)

                label = tk.Label(self, text="- V", font=self.TOP_FONT, bg=self.BG_COLOR, fg=channel.color)
                label.grid(in_=frame, row=1, column=1, padx=self.LABELS_PADX, pady=0, sticky='w')
                # label.pack(pady=0, padx=self.TOP_PADDING[0], in_=frame, side=tkinter.TOP, orient=tkinter.HORIZONTAL)
                self.labels[channel.n]['U'] = label

                label = tk.Label(self, text="- A", font=self.TOP_FONT, bg=self.BG_COLOR, fg=channel.color)
                label.grid(in_=frame, row=1, column=2, padx=self.LABELS_PADX, pady=0, sticky='w')
                #label.pack(pady=0, padx=self.TOP_PADDING[1], in_=frame, side=tkinter.TOP, orient=tkinter.HORIZONTAL)
                self.labels[channel.n]['I'] = label

                label = tk.Label(self, text="- W", font=self.TOP_FONT, bg=self.BG_COLOR, fg=channel.color)
                label.grid(in_=frame, row=2, column=1, padx=self.LABELS_PADX, pady=0, sticky='w')
                # label.pack(pady=0, padx=self.TOP_PADDING[0], in_=frame, side=tkinter.BOTTOM, orient=tkinter.HORIZONTAL)
                self.labels[channel.n]['P'] = label

                label = tk.Label(self, text="- Wh", font=self.TOP_FONT, bg=self.BG_COLOR, fg=channel.color)
                label.grid(in_=frame, row=2, column=2, padx=self.LABELS_PADX, pady=0, sticky='w')
                # label.pack(pady=0, padx=self.TOP_PADDING[1], in_=frame, side=tkinter.BOTTOM, orient=tkinter.HORIZONTAL)
                self.labels[channel.n]['e'] = label

        self.fullscreen_state = False
        if self.desktop:
            self.attributes('-zoomed', True)
            self.toggle_fullscreen()
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
            self.geometry("128x64")
            self.tk.call('tk', 'scaling', 2.0)
        else:
            self.geometry("800x480")
            self.tk.call('tk', 'scaling', 1.0)

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
                self.FG_CHANNEL3 = 'lavender'
            else:
                self.FG_CHANNEL1 = 'green'
                self.FG_CHANNEL2 = 'blue'
                self.FG_CHANNEL3 = 'aqua'

        self.channels[0].color = self.FG_CHANNEL1
        self.channels[1].color = self.FG_CHANNEL2
        self.channels[2].color = self.FG_CHANNEL3

        if self.desktop:
            self.TOP_FONT = ("DejaVu Sans", 28)
            self.PLOT_FONT = {'fontname': 'DejaVu Sans', 'fontsize': 9}
            self.TOP_PADDING = (2, 20)
            self.PLOT_DPI = 200
            self.LABELS_PADX = 10
        else:
            self.TOP_FONT = ("Small Pixel7", 10)
            self.PLOT_FONT = {'fontname': 'Small Pixel7'}
            self.TOP_PADDING = (0, 1)
            self.PLOT_DPI = 43
            self.LABELS_PADX = 1


    def set_screen_update_rate(self, fast=True):
        if fast:
            rate = self.update_speed[0]
        else:
            rate = self.update_speed[1]
        if rate!=self.ani.event_source.interval:
            self.logger.debug('changing update rate %u' % rate)
            self.ani.event_source.interval = rate

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


    def plot_values(self, i):

        num_values = 200

        tmp = []
        if not self.lock.acquire(True, 0.1):
            print('failed to acquire lock')
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


        y_max = 0
        for channel in self.channels:
            if channel.enabled:
                n = len(self.values[channel.n][1])
                if n:
                    x_range = numpy.arange(-n, 0)

                    self.labels[channel.n]['U'].configure(text='%.3fV' % numpy.average(self.values[channel.n][2][-10:]))
                    self.labels[channel.n]['P'].configure(text='%.2fW' % numpy.average(self.values[channel.n][3][-10:]))
                    self.labels[channel.n]['I'].configure(text=self.format(numpy.average(self.values[channel.n][1][-10:]) / 1000, 3, 'A'))
                    self.labels[channel.n]['e'].configure(text=self.format(self.energy[channel.n]['ep'], 3, 'Wh'))
                    # max. for all lines
                    y_max = max(y_max, max(self.values[channel.n][1]))
                    # max. per channel
                    a = max(max(self.values[channel.n][2]) * 1.005, channel.voltage + 0.01)
                    b = min(min(self.values[channel.n][2]) * 0.995, channel.voltage - 0.01)
                    self.lines1[channel.n].set_data(x_range, self.values[channel.n][1])
                    self.lines2[channel.n].set_data(x_range, self.values[channel.n][2])
                    # self.lines1[channel.n].set_data(self.values[channel.n][0], self.values[channel.n][1])
                    # self.lines2[channel.n].set_data(self.values[channel.n][0], self.values[channel.n][2])

                    self.ax[channel.number].set_ylim(top=a, bottom=b)
                    self.ax[channel.number].set_xlim(left=-num_values, right=0)


        if y_max:
            self.ax[0].set_ylim(top=y_max * 1.05, bottom=0)
        self.ax[0].set_xlim(left=-num_values, right=0)

        for ax in self.ax:
            ax.autoscale_view()
            ax.relim()


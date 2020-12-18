#
# Author: sascha_lammers@gmx.de
#

from . import *
from . import Plot
from . import Sensor
from . import Mqtt
from Config.Type import Type
from .AppConfig import Channel
import SDL_Pi_INA3221
from SDL_Pi_INA3221.Calibration import Calibration
import time
import threading
# from threading import Lock
import tkinter
import tkinter as tk
from tkinter import ttk
import tkinter.messagebox
import json
import sys
import math
import matplotlib.animation as animation
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
import time
import threading
import glob
import hashlib
import numpy as np
import copy
# try:
#     import paho.mqtt.client
# except:
#      paho = False
try:
    import pigpio
except:
     pigpio = False
import json
import re
import traceback
import signal

class MainAppCli(Plot.Plot):

    def __init__(self, logger, config, *args, **kwargs):

        Plot.Plot.__init__(self, config)

        self.start_time = time.monotonic()
        self.threads = []
        self.terminate = threading.Event()
        AppConfig._terminate = self.terminate

        self.gui = False
        self.fullscreen_state = False
        self.logger = logger

        # init variables

        self.init_vars()

    def signal_handler(self, signal, frame):
        self.logger.debug('exiting, signal %u...' % signal)
        self.destroy()
        self.quit()
        sys.exit(signal)

    def init_signal_handler(self):
        return
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGKILL, self.signal_handler)

    def init_vars(self):

        Sensor.Sensor.init_vars(self)

        self.channels = Channels()
        # zero based list of enabled channels
        # channel names are '1', '2' and '3'

        for index, channel in AppConfig.channels.items():
            channel.calibration._update_multipliers()
            if channel.enabled:
                self.channels.append(channel)

        self.display_energy = AppConfig.plot.display_energy

        self.labels = [
            {'U': 0, 'e': 0},
            {'U': 0, 'e': 0},
            {'U': 0, 'e': 0}
        ]

        self.ax = []
        self.lines = [
            [],         # for ax[0]
            []          # for ax[1]
        ]

        self.reset_values()
        self.reset_avg()
        self.load_energy()
        self.reset_data()

        # with open('data.json','r') as f:
        #     tmp = json.loads(f.read())
        #     for key, val in tmp.items():
        #         self.values[int(key)] = val


        self.plot_visibility_state = 0
        self.mqtt_connected = False
        self.ignore_wakeup_event = 0
        self.backlight_on = False
        self.time_scale_factor = 0
        self._time_scale_min_time = 5
        self._time_scale_cur = None

    def start(self):

        if AppConfig.mqtt.host:
            if self.init_mqtt():
                thread = threading.Thread(target=self.update_mqtt, args=(), daemon=True)
                thread.start()
                self.threads.append(thread)

        elif AppConfig.headless==True:
            print('MQTT or GUI must be enabled, exiting...')
            sys.exit(-1)

        thread = threading.Thread(target=self.read_sensor, args=(), daemon=True)
        thread.start()
        self.threads.append(thread)

        if AppConfig.backlight.gpio:
            thread = threading.Thread(target=self.backlight_service, args=(), daemon=True)
            thread.start()
            self.threads.append(thread)

        if AppConfig.plot.max_values<200:
            self.logger.warning('plot_max_values < 200, recommended ~400')
        elif AppConfig.plot.max_time<=300 and AppConfig.plot.max_values<AppConfig.plot.max_time:
            self.logger.warning('plot_max_values < plot_max_time. recommended value is plot_max_time * 4 or ~400')

    def destroy(self):
        self.end_mqtt()
        self.terminate.set();

    def quit(self):
        self.logger.debug('end')
        sys.exit(0)

    def loop(self, daemon=False):

        if daemon:
            self.logger.debug('daemonizing...')
            thread = threading.Thread(target=self.loop, args=(False), daemon=True)
            thread.start()
            self.threads.append(thread)
            return

        while not self.terminate.is_set():
            self.logger.debug('ping mainloop')
            self.terminate.wait(60)

        self.logger.debug('waiting for threads to terminate...')
        timeout = time.monotonic() + 10
        count = 1
        while count>0:
            if time.monotonic()<timeout:
                print('PID %u' % os.getpid())
                break
            count = len(self.threads)
            for thread in self.threads:
                if thread.is_alive():
                    thread.join(1)
                else:
                    count -= 1
        self.quit()

    def backlight_service(self):
        if pigpio==False:
            self.logger.error('pigpio not available: backlight support disabled')
            return

        pi = pigpio.pi()
        while not self.terminate.is_set():
            sleep = 2
            if self.fullscreen_state and self.animation_is_running():
                try:
                    dc = pi.get_PWM_dutycycle(AppConfig.backlight.gpio)
                    if dc<10:
                        self.set_screen_update_rate(False)
                        self.backlight_on = False
                    else:
                        self.set_screen_update_rate(True)
                        self.backlight_on = True
                except Exception as e:
                    self.logger.debug('Failed to get duty cycle for GPIO %u' % AppConfig.backlight.gpio)
                    AppConfig._debug_exception(e)
                    sleep = 60
            self.terminate.wait(sleep)

    def create_hass_auto_conf(self, entity, channel, unit, value_json_name, mac_addresses):

        m = hashlib.md5()
        m.update((':'.join([AppConfig.mqtt.device_name, AppConfig.mqtt.MODEL, AppConfig.mqtt.MANUFACTURER, str(channel), entity, value_json_name])).encode())
        unique_id = m.digest().hex()[0:11]

        m = hashlib.md5()
        m.update((':'.join([AppConfig.mqtt.device_name, AppConfig.mqtt.MODEL, AppConfig.mqtt.MANUFACTURER, entity, value_json_name])).encode())
        device_unique_id = m.digest().hex()[0:11]

        connections = []
        for mac_addr in mac_addresses:
            connections.append(["mac", mac_addr])

        return json.dumps({
            'name': '%s-%s-ch%u-%s' % (AppConfig.mqtt.device_name, AppConfig.mqtt.sensor_name, channel, entity),
            'platform': 'mqtt',
            'unique_id': unique_id,
            'device': {
                'name': '%s-%s-%s' % (AppConfig.mqtt.device_name, AppConfig.mqtt.sensor_name, device_unique_id[0:4]),
                'identifiers': [ device_unique_id, '947bc81af46aa573a62ccefadb9c9a7aef6d1c1e' ],
                'connections': connections,
                'model': AppConfig.mqtt.MODEL,
                'sw_version': AppConfig.VERSION,
                'manufacturer': AppConfig.mqtt.MANUFACTURER
            },
            'availability_topic': AppConfig.mqtt.get_status_topic(),
            'payload_available': AppConfig.mqtt.payload_online,
            'payload_not_available': AppConfig.mqtt.payload_offline,
            'state_topic': AppConfig.mqtt.get_channel_topic(channel),
            'unit_of_measurement': unit,
            'value_template': '{{ value_json.%s }}' % value_json_name
        }, ensure_ascii=False, indent=None, separators=(',', ':'))


    def mqtt_publish_auto_discovery(self):
        mac_addresses = Tools.get_mac_addresses()

        for entity, unit in AppConfig.mqtt.AGGREGATED:
            payload = self.create_hass_auto_conf(entity, 0, unit, entity, mac_addresses)
            topic = AppConfig.mqtt.get_auto_discovery_topic(0, entity)
            self.logger.debug('MQTT auto discovery %s: %s' % (topic, payload))
            self.client.publish(topic, payload=payload, qos=AppConfig.mqtt.qos, retain=True)

        for channel in self.channels:
            for entity, unit in AppConfig.mqtt.ENTITIES.items():
                payload = self.create_hass_auto_conf(entity, channel.number, unit, entity, mac_addresses)
                topic = AppConfig.mqtt.get_auto_discovery_topic(channel.number, entity)
                self.logger.debug('MQTT auto discovery %s: %s' % (topic, payload))
                self.client.publish(topic, payload=payload, qos=AppConfig.mqtt.qos, retain=True)

    def on_log(self, client, userdata, level, buf):
        self.logger.debug('%s: %s' % (level, buf))

    def on_connect(self, client, userdata, flags, rc):
        self.logger.debug("MQTT on_connect: %u" % rc)
        self.mqtt_connected = False
        if rc==0:
            self.add_stats('mqtt_con', 1)
            try:
                self.mqtt_connected = True
                self.client.publish(AppConfig.mqtt.get_status_topic(), AppConfig.mqtt.payload_online, qos=AppConfig.mqtt.qos, retain=True)
                if AppConfig.mqtt.auto_discovery:
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

                            topic = AppConfig.mqtt.get_channel_topic(n + 1)
                            self.logger.debug("MQTT publish %s: %s" % (topic, payload))
                            self.client.publish(topic, payload=payload, qos=AppConfig.mqtt.qos, retain=True)


                    payload = json.dumps({
                        'P': self.format_float_precision(sum_data['P']),
                        'E': self.format_float_precision(sum_data['E'] / 1000, kwh_precision),  # E is Wh, we send kWh
                    })
                    topic = AppConfig.mqtt.get_channel_topic(0)
                    self.logger.debug("MQTT publish %s: %s" % (topic, payload))
                    self.client.publish(topic, payload=payload, qos=AppConfig.mqtt.qos, retain=True)

                    self.add_stats('mqtt_pub', 1)

                except Exception as e:
                    self.logger.error('MQTT error: %s: reconnecting...' % e)
                    AppConfig._debug_exception(e)
                    self.client.reconnect()

            self.terminate.wait(AppConfig.mqtt.update_interval)

    def reset_data(self):
        self.data = {'time': [], 0: [], 1: [], 2: []}

    def clear_y_limits(self, n):
        self.y_limits[n] = {
            'y_min': sys.maxsize,
            'y_max': 0,
            'ts': 0
        }

    def add_stats_minmax(self, name, value=0, type='max', reset=False):
        if reset:
            value = type=='min' and sys.maxsize or 0
        if not name in self.stats:
            self.stats[name] = value
        if type=='min':
            self.stats[name] = min(value, self.stats[name])
        else:
            self.stats[name] = max(value, self.stats[name])

    def add_stats(self, name, value, set_value=False):
        if set_value:
            self.stats = value
            return
        if not name in self.stats:
            self.stats[name] = 0
        self.stats[name] += value

    def reset_values(self):

        self.lock.acquire()
        try:
            self.stats = {}
            self.start_time = time.monotonic()
            self.compressed_ts = -1
            self.compressed_min_records = 0
            self.plot_updated = 0
            self.plot_updated_times = []
            self.y_limits = {}
            for i in range(0, 5):
                self.clear_y_limits(i)
            self.power_sum = [ 1 ]
            self.values = PlotValuesContainer(self.channels)
        finally:
            self.lock.release()

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
        print(AppConfig.get_filename(AppConfig.energy_storage_file))
        try:
            with open(AppConfig.get_filename(AppConfig.energy_storage_file), 'r') as f:
                tmp = json.loads(f.read())
                print(tmp)
                self.reset_energy()
                for channel in self.channels:
                    ch = int(channel)
                    t = tmp[str(ch)]
                    self.energy[ch]['t'] = 0
                    self.energy[ch]['ei'] = float(t['ei'])
                    self.energy[ch]['ep'] = float(t['ep'])
        except Exception as e:
            AppConfig._debug_exception(e)
            self.logger.error("failed to load energy: %s" % e)
            self.reset_energy()

    def store_energy(self):
        try:
            self.logger.debug('store energy')
            with open(AppConfig.get_filename(AppConfig.energy_storage_file), 'w') as f:
                tmp = copy.deepcopy(self.energy)
                for channel in self.channels:
                    ch = int(channel)
                    del tmp[ch]['t']
                f.write(json.dumps(tmp))
        except Exception as e:
            self.logger.error("failed to store energy: %s" % e)

class MainApp(MainAppCli, tk.Tk):

    def __init__(self, logger, config):
        global AppConfig
        AppConfig = config

        MainAppCli.__init__(self, logger, config)

        if AppConfig.headless:
            self.logger.debug('starting headless')
            return

        try:
            self.__init_gui__()
        except Exception as e:
            self.logger.error("failed to initialize GUI: %s" % e)
            self.logger.debug('starting headless')
            AppConfig._debug_exception(e)

        self.start()


    def report_callback_exception(self, exc, val, tb):
        if 'shape mismatch' in str(exc):
            self.reset_values()
        else:
            AppConfig._debug_exception(traceback.format_exception(exc, val, tb))

    def __init_gui__(self):

        self.logger.debug('starting with GUI')

        tk.Tk.__init__(self)
        tk.Tk.wm_title(self, "Power Monitor")

        self.gui = True

        if AppConfig._debug:
            tk.Tk.report_callback_exception = self.report_callback_exception

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

        self.plot_visibility_state = 0
        ax = self.fig.add_subplot(self.get_plot_geometry(0), facecolor=self.PLOT_BG)
        ax.autoscale(False)
        ax.margins(0.01, 0.01)
        self.ax.append(ax)

        for channel in self.channels:
            n = self.get_plot_geometry(channel.number)
            self.ax.append(self.fig.add_subplot(n, facecolor=self.PLOT_BG))

        for ax in self.ax:
            ax.grid(True, color=self.PLOT_GRID, axis='both')
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
            ax = self.ax[channel.number]
            ax.ticklabel_format(axis='y', style='plain', scilimits=(0, 0), useOffset=False)
            ax.tick_params(**ticks_params)

        # lines

        self.main_plot_index = MAIN_PLOT.CURRENT
        self.set_main_plot()

        for channel in self.channels:
            ax = self.ax[channel.number]
            line, = ax.plot(self.values.time(), self.values[channel].voltage(), color=channel._color_for('U'), label=channel.name + ' U', linewidth=2)
            self.lines[1].append(line)



        self.legend()

        # top labels

        label_font_size = [32, 28, 18]
        label_config = {
            'font': (self.TOP_FONT, label_font_size[len(self.channels) - 1]),
            'bg': self.BG_COLOR,
            'fg': 'white',
            'anchor': 'center'
        }

        # top frame for enabled channels
        # 1 colum per active channel
        top_frames = [
            { 'relx': 0.0, 'rely': 0.0, 'relwidth': 1.0, 'relheight': 0.12 },
            { 'relx': 0.0, 'rely': 0.0, 'relwidth': 0.5, 'relheight': 0.17 },
            { 'relx': 0.0, 'rely': 0.0, 'relwidth': 0.33, 'relheight': 0.17 }
        ]
        top_frame = top_frames[len(self.channels) - 1]

        # add plot to frame before labels for the z order

        self.canvas = FigureCanvasTkAgg(self.fig, self)
        self.canvas.draw()
        # self.canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=0, padx=0)
        self.canvas.get_tk_widget().pack()

        gui = {}
        try:
            with open(AppConfig.get_filename(self.get_gui_config_filename()), 'r') as f:
                gui = json.loads(f.read())
        except Exception as e:
            self.logger.debug('failed to write GUI config: %s' % e)
            gui = {}

        gui['geometry'] = self.geometry_info

        padding_y = { 1: 100, 2: 70, 3: 70 }
        pady = -1 / padding_y[len(self.channels)]
        padx = -1 / 50
        y = top_frame['relheight'] + pady
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

        self.ani_interval = AppConfig.plot.refresh_interval
        self.canvas.get_tk_widget().place(in_=top, **plot_placement)
        self.ani = animation.FuncAnimation(self.fig, self.plot_values, interval=ANIMATION.INIT)

        # label placement for the enabled channels
        if 'label_places' in gui:
            places = gui['label_places'].copy()
        else:
            places = []
            pad = 1 / 200
            pad2 = pad * 2
            if len(self.channels)==1:
                # 1 row 4 cols
                w = 1 / 4
                h = 1.0
                for i in range(0, 4):
                    x = i / 4
                    places.append({'relx': x + pad, 'rely': pad, 'relwidth': w - pad2, 'relheight': h - pad2})
            elif len(self.channels)==2:
                # 2x 2 row 2 cols
                w = 1 / 2
                h = 1 / 2
                for i in range(0, 8):
                    x = (i % 2) / 2
                    y = (int(i / 2) % 2) * h
                    places.append({'relx': x + pad, 'rely': y + pad, 'relwidth': w - pad2, 'relheight': h - pad2})
            elif len(self.channels)==3:
                # 3x 2 row 2 cols
                w = 1 / 3
                h = 1 / 2
                for i in range(0, 12):
                    x = (i % 2) / 3
                    y = (int(i / 2) % 2) * h
                    places.append({'relx': x + pad, 'rely': y + pad, 'relwidth': w - pad2, 'relheight': h - pad2})
            gui['label_places'] = places.copy()

        for channel in self.channels:
            ch = int(channel)
            label_config['fg'] = channel.color

            frame = tk.Frame(self, bg=self.BG_COLOR)
            frame.pack()
            frame.place(in_=top, **top_frame)
            top_frame['relx'] += top_frame['relwidth']

            label = tk.Label(self, text="- V", **label_config)
            label.pack(in_=frame)
            label.place(in_=frame, **places.pop(0))
            self.labels[ch]['U'] = label

            label = tk.Label(self, text="- A", **label_config)
            label.pack(in_=frame)
            label.place(in_=frame, **places.pop(0))
            self.labels[ch]['I'] = label

            label = tk.Label(self, text="- W", **label_config)
            label.pack()
            label.place(in_=frame, **places.pop(0))
            self.labels[ch]['P'] = label

            label = tk.Label(self, text="- Wh", **label_config)
            label.pack()
            label.place(in_=frame, **places.pop(0))
            self.labels[ch]['e'] = label

        frame = tk.Frame(self, bg='#999999')
        frame.pack()
        frame.place(in_=top, relx=0.5, rely=2.0, relwidth=0.75, relheight=0.25, anchor='center')
        self.popup_frame = frame
        label = tk.Label(self, text="", font=('Verdana', 32), bg='#999999', fg='#ffffff', anchor='center')
        label.pack(in_=self.popup_frame, fill=tkinter.BOTH, expand=True)
        self.popup_label = label
        self.popup_hide_timeout = None

        if AppConfig._debug:
            label = tk.Label(self, text="", font=('Verdana', 12), bg='#333333', fg=self.TEXT_COLOR, anchor='nw', wraplength=800)
            label.pack()
            label.place(in_=top, relx=0.0, rely=1.0-0.135 + 2.0, relwidth=1.0, relheight=0.13)
            self.debug_label = label
            self.debug_label_state = 2


        try:
            with open(AppConfig.get_filename(self.get_gui_config_filename(True)), 'w') as f:
                f.write(json.dumps(gui, indent=2))
        except Exception as e:
            self.logger.debug('failed to write GUI config: %s' % e)

        if AppConfig.gui.fullscreen:
            self.attributes('-zoomed', True)
            self.toggle_fullscreen()

        if AppConfig.backlight.gpio:
            self.bind("<Enter>", self.wake_up)
            self.bind("<Leave>", self.wake_up)
            self.bind("<Motion>", self.wake_up)

        self.canvas.get_tk_widget().bind('<Button-1>', self.button_1)

        self.bind("<Control-t>", self.store_values)
        self.bind("<F1>", lambda a: self.reset_values())
        self.bind("<F2>", self.toggle_plot)
        self.bind("<F3>", self.toggle_main_plot)
        self.bind("<F4>", self.toggle_display_energy)
        self.bind("<F8>", self.reload_gui)
        # self.bind("<F9>", self.reload_config)
        self.bind("<F10>", self.toggle_debug)
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self.end_fullscreen)

    def destroy(self):
        MainAppCli.destroy(self)
        try:
            tk.Tk.destroy(self)
        except Exception as e:
            self.logger.error(e)
            pass

    def mainloop(self):
        self.logger.debug('mainloop gui=%s' % self.gui)
        if self.gui:
            tk.Tk.mainloop(self)
        else:
            MainAppCli.loop(self, False)

    def quit(self):
        try:
            tk.Tk.quit(self)
        except Exception as e:
            self.logger.error(e)
            pass
        MainAppCli.quit(self)

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
            self.FG_CHANNEL0 = 'white'
            self.FG_CHANNEL1 = 'white'
            self.FG_CHANNEL2 = 'white'
            self.FG_CHANNEL3 = 'white'
        else:
            if self.color_schema_dark:
                self.FG_CHANNEL0 = 'red'
                self.FG_CHANNEL1 = 'lime'
                self.FG_CHANNEL2 = 'deepskyblue'
                self.FG_CHANNEL3 = '#b4b0d1' # 'lavender'
            else:
                self.FG_CHANNEL0 = 'red'
                self.FG_CHANNEL1 = 'green'
                self.FG_CHANNEL2 = 'blue'
                self.FG_CHANNEL3 = 'aqua'

        Channel.COLOR_AGGREGATED_POWED = self.FG_CHANNEL0
        AppConfig.channels[0].color = self.FG_CHANNEL1
        AppConfig.channels[1].color = self.FG_CHANNEL2
        AppConfig.channels[2].color = self.FG_CHANNEL3

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

    def animation_set_state(self, pause=True, interval=None):
        self.lock.acquire()
        try:
            is_running = self.animation_is_running()
            self.logger.debug('animation_set_state pause=%s interval=%u set=%s is_running=%s' % (pause, self.ani_interval, str(interval), is_running))
            if pause:
                if is_running:
                    self.logger.debug('stopping animation')
                    self.ani.event_source.stop()
                self.ani.event_source.interval = ANIMATION.PAUSED
            else:
                if interval!=None:
                    self.ani_interval = interval
                self.ani.event_source.interval = self.ani_interval
                if not is_running:
                    self.logger.debug('starting animation')
                    self.ani.event_source.start()
        finally:
            self.lock.release()

    def animation_get_state(self):
        if self.ani.event_source.interval in ANIMATION.STATES:
            return self.ani.event_source.interval
        return ANIMATION.RUNNING

    def animation_is_running(self):
        return not self.ani.event_source.interval in ANIMATION.STATES

    def animation_compare_interval(self, interval):
        return self.animation_is_running() and self.ani_interval==interval

    def set_screen_update_rate(self, fast=True):
        if fast:
            rate = AppConfig.plot.refresh_interval
        else:
            rate = AppConfig.plot.idle_refresh_interval

        if not self.animation_is_running(): # set rate if paused
            self.logger.debug('changing animation update rate: %u (paused)' % rate)
            self.ani_interval = rate
            return

        if not self.animation_compare_interval(rate):
            self.logger.debug('changing animation update rate: %u' % rate)
            self.animation_set_state(False, rate)
        # else:
            # self.logger.debug('animation update rate already set: %u' % rate)

    def get_gui_config_filename(self, auto=''):
        if auto==True:
            auto = '-auto'
        return 'gui-%u-%ux%u%s.json' % (len(self.channels), self.geometry_info[0], self.geometry_info[1], auto)

    def toggle_debug(self, event=None):
        self.debug_label_state = (self.debug_label_state + 1) % 3
        if self.debug_label_state==0:
            self.debug_label.place(rely=1.0-0.135, relheight=0.13)
            self.debug_label.configure(font=('Verdana', 10))
        if self.debug_label_state==1:
            self.debug_label.place(rely=1.0-0.255, relheight=0.25)
            self.debug_label.configure(font=('Verdana', 18))
        if self.debug_label_state==2:
            self.debug_label.place(rely=1.1, relheight=0.1)
        return 'break'


    def reload_gui(self, event=None):
        try:
            with open(AppConfig.get_filename(self.get_gui_config_filename()), 'r') as f:
                gui = json.loads(f.read())

            self.canvas.get_tk_widget().place(**gui['plot_placement'])

            places = gui['label_places']
            for channel in self.channels:
                if channel.enabled:
                    self.labels[channel]['U'].place(**places.pop(0))
                    self.labels[channel]['I'].place(**places.pop(0))
                    self.labels[channel]['P'].place(**places.pop(0))
                    self.labels[channel]['e'].place(**places.pop(0))

        except Exception as e:
            self.logger.error('Reloading GUI failed: %s' % e)
        return "break"

    def reload_config(self, event=None):
        try:
            ConfigLoader.ConfigLoader.load_config()
        except Exception as e:
            self.logger.error('Reloading configuration failed: %s' % e)
        return "break"

    def button_1(self, event):

        x = int(event.x / (self.geometry_info[0] / 3))
        y = int(event.y / (self.geometry_info[1] / 2))


        self.logger.debug('button1 %u:%u' % (x, y))

        if x==0:
            self.toggle_plot()
        elif x==1:
            self.toggle_time_scale()
        else:
            self.toggle_main_plot()

    def toggle_time_scale(self, event=None):
        num = self.get_time_scale_num()
        self.time_scale_factor += 1
        self.time_scale_factor %= num
        n = self.get_time_scale(num)
        self.legend()
        self.show_popup('%u of %u seconds (%u/%u)' % (n, AppConfig.plot.max_time, self.time_scale_factor + 1, num))
        # self.logger.debug('time scale=%u' % self.get_time_scale(True))
        return "break"


    def show_popup(self, msg, timeout=3.5):
        if msg==None:
            self.popup_hide_timeout = None
            self.popup_frame.place(rely=2.0)
        else:
            self.popup_hide_timeout = time.monotonic() + timeout
            self.popup_label.configure(text=msg)
            self.popup_frame.place(rely=0.28)

    def store_values(self, event=None):
        fn = 'data-%u.json' % int(time.monotonic())
        self.logger.debug('stored values in %s' % fn)
        with open(fn, 'w') as f:
            f.write(json.dumps(self.values, indent=2))
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

    def debug_bind(self, event=None):
        self.logger.debug(event)
        return "break"

    def wake_up(self, event=None):
        if AppConfig.mqtt.motion_payload!='' and self.backlight_on==False and self.mqtt_connected:
            t = time.monotonic()
            if t>self.ignore_wakeup_event:
                self.logger.debug('MQTT wake up event')
                self.client.publish(AppConfig.mqtt.get_motion_topic(t), payload=AppConfig.mqtt.motion_payload, qos=AppConfig.mqtt.qos, retain=AppConfig.mqtt.motion_retain)
                self.ignore_wakeup_event = time.monotonic() + AppConfig.mqtt.motion_repeat_delay
                self.set_screen_update_rate(self.fullscreen_state)
        return "break"

    def end_fullscreen(self, event=None):
        self.fullscreen_state = False
        self.attributes("-fullscreen", False)
        self.config(cursor='')
        self.set_screen_update_rate(False)
        return "break"

    def toggle_animation(self, event=None):
        self.logger.debug('toggle_animation running=%s' % self.animation_is_running())
        self.animation_set_state(pause=self.animation_is_running())
        return 'break'

    def toggle_plot(self, event=None):
        self.plot_visibility_state = (self.plot_visibility_state + 1) % 3
        idx = 0
        for ax in self.ax:
            n = self.get_plot_geometry(idx)
            if n!=None:
                ax.set_visible(True)
                ax.change_geometry(int(n / 100) % 10, int(n / 10) % 10, int(n) % 10)
            elif ax:
                ax.set_visible(False)
            idx += 1
        self.canvas.draw()
        return 'break'

    def toggle_main_plot(self, event=None):
        self.main_plot_index = (self.main_plot_index + 1) % 3
        self.set_main_plot()
        return 'break'

    def toggle_display_energy(self, event=None):
        if self.display_energy==DISPLAY_ENERGY.AH:
            self.display_energy=DISPLAY_ENERGY.WH
        else:
            self.display_energy=DISPLAY_ENERGY.AH
        return 'break'

    def get_plot_values(self, axis, channel):
        if axis==0:
            if self.main_plot_index==MAIN_PLOT.CURRENT:
                return (self.values.time(), self.values[channel], self.values[channel].current())
            elif self.main_plot_index==MAIN_PLOT.POWER:
                return (self.values.time(), self.values[channel], self.values[channel].power())
            elif self.main_plot_index==MAIN_PLOT.AGGREGATED_POWER:
                tidx = self.values.time()
                # if len(self.power_sum)!=len(tidx):
                #     self.power_sum = np.zeros(tidx)
                return (tidx, self.values[0], self.power_sum)
        elif axis==1:
            return (self.values.time(), self.values[channel], self.values[channel].voltage())
        raise RuntimeError('axis %u channel %u main_plot_index %u' % (axis, channel, self.main_plot_index))

    def get_plot_line(self, axis, channel):
        if axis==0:
            if self.main_plot_index==MAIN_PLOT.CURRENT or self.main_plot_index==MAIN_PLOT.POWER:
                return self.lines[0][channel]
            elif self.main_plot_index==MAIN_PLOT.AGGREGATED_POWER:
                return self.lines[0][0]
        elif axis==1:
            return self.lines[1][channel]
        raise RuntimeError('axis %u channel %u main_plot_index %u' % (axis, channel, self.main_plot_index))

    def set_main_plot(self):
        if not self.lock.acquire(True):
            return
        try:
            self.power_sum = []
            self.clear_y_limits(0)
            if self.main_plot_index==MAIN_PLOT.CURRENT:
                values_type = 'I'
                x_range, values, items = self.get_plot_values(0, 0)
                self.plot_main_current_rounding = AppConfig.plot.main_current_rounding
                self.ax[0].set_ylabel('Current (A)', color=self.PLOT_TEXT, **self.PLOT_FONT)
            elif self.main_plot_index==MAIN_PLOT.POWER:
                values_type = 'P'
                x_range, values, items = self.get_plot_values(0, 1)
                self.plot_main_current_rounding = AppConfig.plot.main_current_rounding
                self.ax[0].set_ylabel('Power (W)', color=self.PLOT_TEXT, **self.PLOT_FONT)
            elif self.main_plot_index==MAIN_PLOT.AGGREGATED_POWER:
                values_type = 'Psum'
                x_range, values, items = self.get_plot_values(0, 2)
                self.plot_main_current_rounding = AppConfig.plot.main_power_rounding
                self.ax[0].set_ylabel('Aggregated Power (W)', color=self.PLOT_TEXT, **self.PLOT_FONT)

            self.lines[0] = []
            for line in self.ax[0].get_lines():
                line.remove()

            if self.main_plot_index==4:
                line, = self.ax[0].plot(x_range, values, color=channel._color_for(values_type), label='Power', linewidth=AppConfig.plot.line_width)
                self.lines[0].append(line)
            else:
                for channel in self.channels:
                    line, = self.ax[0].plot(self.values.time(), self.values[channel].voltage(), color=channel._color_for(values_type), label=channel.name, linewidth=AppConfig.plot.line_width)
                    self.lines[0].append(line)

            self.add_ticks()

        finally:
            self.lock.release()

    # def _debug_validate_length(self):
    #     if AppConfig._debug:
    #         lens = []
    #         for type, ch, items in self.values.all():
    #             lens.append(len(items))
    #         if sum(lens)/len(lens)!=lens[0]:
    #             raise RuntimeError('array length mismatch: %s' % (lens))

    def min_max_downsample(self, x, y, num_bins, do_x=True):
        pts_per_bin = y.size // num_bins

        if do_x:
            x_view = x.reshape(num_bins, pts_per_bin)
        y_view = y.reshape(num_bins, pts_per_bin)
        i_min = np.argmin(y_view, axis=1)
        i_max = np.argmax(y_view, axis=1)

        r_index = np.repeat(np.arange(num_bins), 2)
        c_index = np.sort(np.stack((i_min, i_max), axis=1)).ravel()

        if do_x:
            return x_view[r_index, c_index]
        return y_view[r_index, c_index]

    def compress_values(self):

        try:
            t = time.monotonic()

            # remove old data
            diff_t = self.values.timeframe()
            if diff_t>AppConfig.plot.max_time:
                idx = self.values.find_time_index(AppConfig.plot.max_time)
                # self.logger.debug('discard 0:%u' % (idx + 1))
                # discard from all lists
                for type, ch, items in self.values.all():
                    self.values.set_items(type, ch, items[idx + 1:])

            # compress data if min records have been added
            if self.compressed_min_records<AppConfig.plot.compression.min_records:
                return

            start_idx = self.values.find_time_index(self.compressed_ts, True)
            if start_idx==None:
                return
            end_idx = self.values.find_time_index(AppConfig.plot.compression.uncompressed_time)
            if end_idx==None:
                return
            values_per_second = AppConfig.plot.max_values / float(AppConfig.plot.max_time)
            count = end_idx - start_idx
            timeframe = self.values.timeframe(start_idx, end_idx)
            groups = timeframe * values_per_second
            if groups==0:
                return
            # split data into groups of group_size
            group_size = int(count / groups)
            if group_size>=4 and count>group_size*2:
                # find even count
                while count % group_size != 0:
                    count -= 1
                    end_idx -= 1
                n = count / group_size

                self.logger.debug('compress group_size=%u data=%u:%u#%u vps=%.2f' % (group_size, start_idx, end_idx, count, values_per_second))

                old_timestamp = self.compressed_ts
                # store timestamp
                self.compressed_ts = self.values.time()[end_idx]
                self.compressed_min_records = 0

                before = len(self.values._t)

                # split array into 3 array and one of them into groups and generate mean values for each group concatenation the flattened result
                for type, ch, items in self.values.all():

                    self.add_stats('ud', len(items))

                    items = np.array_split(items[:], [start_idx, end_idx])
                    items[1] = np.array(items[1])
                    items[1] = self.min_max_downsample(items[1], items[1], group_size, type=='t')

                    items[1] = np.array(items[1]).reshape(-1, group_size).mean(axis=0)

                    tmp = np.concatenate(np.array(items, dtype=object).flatten()).tolist()
                    self.values.set_items(type, ch, tmp)

                    self.add_stats('cd', len(tmp))

                diff = time.monotonic() - t

                self.add_stats('cr', before - len(self.values._t))
                self.add_stats('ct', diff)

        except Exception as e:
            AppConfig._debug_exception(e)

    def aggregate_sensor_values(self):

        try:
            tmp = []
            if not self.lock.acquire(True, 0.1):
                return
            try:
                tmp = self.data.copy();
                tmp2 = self.averages.copy()
                self.reset_data()
            finally:
                self.lock.release()

            n = len(tmp['time'])
            if n==0:
                return

            self.compressed_min_records += n
            self.values.append_time(tmp['time'])
            for channel in self.channels:
                U = self.values[channel].voltage()
                I = self.values[channel].current()
                P = self.values[channel].power()
                for current, loadvoltage, power in tmp[int(channel)]:
                    U.append(loadvoltage)
                    I.append(current)
                    P.append(power)

            self.compress_values()
        except Exception as e:
            AppConfig._debug_exception(e)

    def plot_count_fps(self):
        ts = time.monotonic()
        self.plot_updated_times.append(ts - self.plot_updated)
        if len(self.plot_updated_times)>20:
            self.plot_updated_times.pop(0)
        self.plot_updated = ts

    def get_plot_fps(self):
        return 1.0/ max(0.000001, len(self.plot_updated_times)>2 and np.average(self.plot_updated_times[1:]) or 0)

    def plot_values(self, i):

        if i<=1:
            if self.ani.event_source.interval==ANIMATION.INIT:
                # stop animation after initializing
                # the first sensor data will start it
                self.logger.debug('animation ready...')
                self.ani.event_source.stop()
                self.ani.event_source.interval = ANIMATION.READY
            return

        try:
            self.aggregate_sensor_values()

            fmt = FormatFloat.FormatFloat(4, 5, prefix=FormatFloat.PREFIX.M, strip=FormatFloat.STRIP.NONE)
            fmt.set_precision('m', 1)

            self.plot_count_fps()

            ts = time.monotonic()
            display_idx = 0
            x_max = None
            x_min = -self.get_time_scale()
            y_max = 0
            y_min = sys.maxsize

            if self.main_plot_index==MAIN_PLOT.AGGREGATED_POWER:
                tmp = []
                for channel in self.channels:
                    ch = int(channel)
                    tmp.append(self.values[ch].power())
                self.power_sum = np.array(tmp).sum(axis=0)

            for channel in self.channels:
                ch = int(channel)

                # axis 0
                line = self.get_plot_line(0, ch)
                x_range, values, items = self.get_plot_values(0, ch)
                if x_max==None:
                    x_max = self.values.max_time()
                    x_min = x_max - self.get_time_scale()
                    display_idx = self.values.find_time_index(x_min, True)

                # top labels
                self.labels[ch]['U'].configure(text=fmt.format(values.avg_U(), 'V'))
                self.labels[ch]['I'].configure(text=fmt.format(values.avg_I(), 'A'))
                self.labels[ch]['P'].configure(text=fmt.format(values.avg_P(), 'W'))
                tmp = self.display_energy==DISPLAY_ENERGY.AH and ('ei', 'Ah') or ('ep', 'Wh')
                self.labels[ch]['e'].configure(text=fmt.format(self.energy[ch][tmp[0]], tmp[1]))

                # axis 1
                # if self.main_plot_index!=MAIN_PLOT.AGGREGATED_POWER:
                # max. for all lines
                y_max = max(y_max, max(items[display_idx:]))
                y_min = min(y_min, min(items[display_idx:]))
                line.set_data(x_range, items)

                x_range, values, items = self.get_plot_values(1, ch)
                line = self.get_plot_line(1, ch)
                line.set_data(x_range, items)

                # max. per channel
                y_max1 = max(Tools.fround(values.max_U(display_idx) * AppConfig.plot.voltage_top_margin, 2), channel.voltage + 0.02)
                y_min1 = min(Tools.fround(values.min_U(display_idx) * AppConfig.plot.voltage_bottom_margin, 2), channel.voltage - 0.02)
                self.ax[channel.number].set_ylim(top=y_max1, bottom=y_min1)


            # # axis 0 power sum
            # if self.main_plot_index==4:
            #     self.power_sum = [sum(x) for x in zip(*power_sum)]
            #     y_max = max(self.power_sum)
            #     self.get_plot_line(0, 0).set_data(x_range, power_sum);
                # self.lines[0][0].set_data(x_range, power_sum);

            # axis 0 y limits
            if y_min==sys.maxsize:
                y_min=0
            if y_max:
                # t=[y_max, y_min]
                y_max = Tools.fround(y_max * AppConfig.plot.main_top_margin / self.plot_main_current_rounding) * self.plot_main_current_rounding
                y_min = max(0, Tools.fround(y_min * AppConfig.plot.main_bottom_margin / self.plot_main_current_rounding) * self.plot_main_current_rounding)
                if y_max == y_min:
                    y_max += self.plot_main_current_rounding

                # limit y axis scaling to 5 seconds and a min. change of 5% except for increased limits
                yl2 = self.y_limits[0]
                ml = (yl2['y_max'] - yl2['y_min']) * AppConfig.plot.main_y_limit_scale_value
                if y_max>yl2['y_max'] or y_min<yl2['y_min'] or (ts>yl2['ts'] and (y_min>yl2['y_min']+ml or y_min<yl2['y_max']-ml)):
                    # self.logger.debug('limits %s' % ([yl2,y_min,y_max,ts,ml]))
                    yl2['y_min'] = y_min
                    yl2['y_max'] = y_max
                    yl2['ts'] = ts + AppConfig.plot.main_y_limit_scale_time
                    self.ax[0].set_ylim(top=y_max, bottom=y_min)

                    # plt.xticks(np.arange(min(x), max(x)+1, 1.0))

            # shared x limits for all axis
            if x_max!=None:
                for ax in self.ax:
                    ax.set_xlim(left=x_max-self.get_time_scale(), right=x_max)


            # for ax in self.ax:
            #     ax.autoscale_view()
            #     ax.relim()


            if self.popup_hide_timeout!=None and ts>self.popup_hide_timeout:
                self.show_popup(None)

            # DEBUG DISPLAY

            if AppConfig._debug:
                data_n = 0
                for channel, values in self.values.items():
                    for type, items in values.items():
                        data_n += len(items)
                    # parts.append('%u:#%u' % (channel, len(values[0])))
                    # for i in range(0, len(values)):
                    #     data_n += len(values[i])

                p = [
                    'fps=%.2f' % self.get_plot_fps(),
                    'data=%u' % data_n
                ]
                for key, val in self.stats.items():
                    if isinstance(val, float):
                        val = '%.4f' % val
                    p.append('%s=%s' % (key, val))

                p.append('comp_rrq=%u' % (self.compressed_min_records<AppConfig.plot.compression.min_records and (AppConfig.plot.compression.min_records - self.compressed_min_records) or 0))

                self.debug_label.configure(text=' '.join(p))

        except ValueError as e:

            self.logger.error('%s' % e)

        except Exception as e:
            AppConfig._debug_exception(e)


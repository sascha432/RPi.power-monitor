#
# Author: sascha_lammers@gmx.de
#

from . import *
# from . import BaseApp
# from . import Plot
# from . import Sensor
# from . import Mqtt
from Config.Type import Type
from .AppConfig import Channel
import SDL_Pi_INA3221
from SDL_Pi_INA3221.Calibration import Calibration
import sys
import time
import numpy as np
import json

class GuiConfig(object):

    def __init__(self, parent=None, data={}, allowed=None, exception=False):
        object.__setattr__(self, '_parent', parent)
        object.__setattr__(self, '_allowed', allowed)
        object.__setattr__(self, '_exception', exception)
        for key, val in data.items():
            object.__setattr__(self, key, val)
        if allowed:
            for key in allowed:
                if not hasattr(self, key):
                    object.__setattr__(self, key, data[key])

    def __setattr__(self, key, val):
        if not key.startswith('_'):
            self._parent.write_gui_config()
            if self._allowed==None:
                return
            if not key in self._allowed:
                if self._exception:
                    KeyError('GuiConfig: cannot set attribute %s' % (key))
                return
        object.__setattr__(self, key, val)

    def _asdict(self):
        tmp = {}
        if self._allowed:
            for key in self._allowed:
                if not key.startswith('_'):
                    val = getattr(self, key)
                    s = str(val)
                    if not isinstance(val, float) and '.' in s:
                        s = s.split('.')[-1]
                    tmp[key] = s
        print(tmp)
        return tmp

class MainAppCli(Plot.Plot):
    def __init__(self):
        self.fullscreen_state = False

    def start(self):
        self.debug(__name__, 'start')
        if AppConfig.plot.max_values<200:
            self.warning(__name__, 'plot_max_values < 200, recommended ~400')
        elif AppConfig.plot.max_time<=300 and AppConfig.plot.max_values<AppConfig.plot.max_time:
            self.warning(__name__, 'plot_max_values < plot_max_time. recommended value is plot_max_time * 4 or ~400')

    def init_vars(self):
        self.debug(__name__, 'init_vars')

        self._gui_config = None
        self.channels = Channels()
        # zero based list of enabled channels
        # channel names are '1', '2' and '3'

        for index, channel in AppConfig.channels.items():
            channel.calibration._update_multipliers()
            if channel.enabled:
                self.channels.append(channel)

        self.labels = [
            {'U': 0, 'e': 0},
            {'U': 0, 'e': 0},
            {'U': 0, 'e': 0}
        ]

        self.ax = []
        self.lines = [ [], [] ] # lines for ax[0], ax[1]

        self.reset_values()
        self.reset_avg()
        self.load_energy()
        self.reset_data()

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


    def clear_y_limits(self, n):
        self._y_limits[n] = [sys.maxsize, 0, 0] # min max timestamp

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
        self.reset_data()
        try:
            self.stats = {}
            self.start_time = time.monotonic()
            self.compressed_ts = -1
            self.compressed_min_records = 0
            self.plot_updated = 0
            self.plot_updated_times = []
            self._y_limits = [()]*4
            for i in range(0, 4):
                self.clear_y_limits(i)
            self.power_sum = [ 1 ]
            self.values = PlotValuesContainer(self.channels)
        finally:
            self.lock.release()

    def reset_energy(self):
        self.energy = {
            0: {'t': 0, 'ei': 0, 'ep': 0},
            1: {'t': 0, 'ei': 0, 'ep': 0},
            2: {'t': 0, 'ei': 0, 'ep': 0},
            'stored': 0,
        }

class MainApp(MainAppCli):

    def __init__(self, logger, app_config):
        global AppConfig
        AppConfig = app_config

        self._gui = None
        self._logger = logger
        self._app_config = app_config
        self._bases = Tools.get_bases(self.__module__, self.__class__.__qualname__)

        class LambdaCaller:
            def __init__(self, self_obj, func_name):
                self._func_name = func_name
                self._self_obj = self_obj
            def __call__(self, *args, **kwargs):
                Tools.execute_method(self._self_obj, self._self_obj._bases, self._func_name, *args, **kwargs)

        for func_name in ('start', 'destroy', 'reload', 'init_vars'):
            obj = LambdaCaller(self, func_name)
            setattr(self, func_name, obj)

        for class_type in self._bases:
            self.debug(__name__, '%s.__init__()', class_type)
            class_type.__init__(self)

        self.init_vars()

        try:
            if AppConfig.headless:
                raise RuntimeWarning('failed to initialize GUI in debug mode. this warning is raised with headless=True')
            self.__init_gui__()
        except Exception as e:
            self._gui = None
            if not AppConfig.headless:
                self.error(__name__, 'failed to initialize GUI: %s', e)
            self.debug(__name__, 'starting headless')
            AppConfig._debug_exception(e)

        self.start()

    def _execute_base_methods(self_obj, func_name, *args, **kwargs):
        self_obj.debug(__name__, 'calling __bases__.%s', func_name)
        Tools.execute_method(self_obj, self_obj._bases, func_name, *args, **kwargs)

    def read_gui_config(self):
        defaults = {
            'plot_visibility': PLOT_VISIBILITY.BOTH,
            'plot_primary_display': PLOT_PRIMARY_DISPLAY.CURRENT,
            'plot_display_energy': DISPLAY_ENERGY.WH, #AppConfig.plot.display_energy,
            'plot_time_scale': 1.0
        }
        try:
            file = AppConfig.get_filename('config_state.json')
            self.debug(__name__, 'read gui config %s', file)
            with open(file, 'r') as f:
                data = json.loads(f.read())
                self._gui_config = GuiConfig(self, data, defaults.keys())
        except Exception as e:
            self.info(__name__, 'failed to load: %s: %s', file, e)
            self._gui_config = GuiConfig(self, defaults, defaults.keys())

        try:
            self._gui_config.plot_visibility = Tools.EnumFromStr(PLOT_VISIBILITY, self._gui_config.plot_visibility)
            self._gui_config.plot_display_energy = Tools.EnumFromStr(DISPLAY_ENERGY, self._gui_config.plot_display_energy)
            self._gui_config.plot_primary_display = Tools.EnumFromStr(PLOT_PRIMARY_DISPLAY, self._gui_config.plot_primary_display)
            self._gui_config.plot_time_scale = max(0, min(1, float(self._gui_config.plot_time_scale)))
        except Exception as e:
            self.info(__name__, 'invalid configuration: %s: %s', file, e)
            self._gui_config = GuiConfig(self, defaults, defaults.keys())


    def _write_gui_config(self):
        try:
            file = AppConfig.get_filename('config_state.json')
            self.debug(__name__, 'write gui config %s', file)
            with open(file, 'w') as f:
                f.write(json.dumps(self._gui_config._asdict()))
        except Exception as e:
            self.error(__name__, 'failed to store: %s: %s', file, e)

    def write_gui_config(self):
        for item in self._scheduler.queue:
            if getattr(item, 'priority')==SCHEDULER_PRIO.WRITE_GUI_CONFIG:
                self._scheduler.cancel(item)
        self._scheduler.enter(10.0, SCHEDULER_PRIO.WRITE_GUI_CONFIG, self._write_gui_config)

    def __init_gui__(self):

        self.debug(__name__, 'starting with GUI')

        def import_gui():
            global Gui, tk, ttk, tkinter, animation, Figure, FigureCanvasTkAgg, NavigationToolbar2Tk
            from .Gui import Gui
            import tkinter
            import tkinter as tk
            from tkinter import ttk
            import tkinter.messagebox
            import matplotlib.animation as animation
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)

        import_gui()

        self.read_gui_config()

        self._gui = Gui(self)

        # set to false for OLED
        self.desktop = True
        self.color_schema_dark = True
        self.monochrome = False

        # color scheme and screen size
        self.init_scheme()

        # init TK

        self._gui.configure(bg=self.BG_COLOR)

        top = tk.Frame(self._gui)
        top.pack(side=tkinter.TOP)
        top.place(relwidth=1.0, relheight=1.0)

        # plot

        self.fig = Figure(figsize=(3, 3), dpi=self.PLOT_DPI, tight_layout=True, facecolor=self.BG_COLOR)

        # axis

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

        # self.ax[0].set_ylabel('Current (A)', color=self.PLOT_TEXT, **self.PLOT_FONT)
        self.ax[0].tick_params(**ticks_params)

        for channel in self.channels:
            ax = self.ax[channel.number]
            ax.ticklabel_format(axis='y', style='plain', scilimits=(0, 0), useOffset=False)
            ax.tick_params(**ticks_params)

        # lines

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

        self.canvas = FigureCanvasTkAgg(self.fig, self._gui)
        self.canvas.draw()
        # self.canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=0, padx=0)
        self.canvas.get_tk_widget().pack()

        gui = {}
        try:
            with open(AppConfig.get_filename(self.get_gui_scheme_config_filename()), 'r') as f:
                gui = json.loads(f.read())
        except Exception as e:
            self.debug(__name__, 'failed to write GUI config: %s', e)
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

            frame = tk.Frame(self._gui, bg=self.BG_COLOR)
            frame.pack()
            frame.place(in_=top, **top_frame)
            top_frame['relx'] += top_frame['relwidth']

            label = tk.Label(self._gui, text="- V", **label_config)
            label.pack(in_=frame)
            label.place(in_=frame, **places.pop(0))
            self.labels[ch]['U'] = label

            label = tk.Label(self._gui, text="- A", **label_config)
            label.pack(in_=frame)
            label.place(in_=frame, **places.pop(0))
            self.labels[ch]['I'] = label

            label = tk.Label(self._gui, text="- W", **label_config)
            label.pack()
            label.place(in_=frame, **places.pop(0))
            self.labels[ch]['P'] = label

            label = tk.Label(self._gui, text="- Wh", **label_config)
            label.pack()
            label.place(in_=frame, **places.pop(0))
            self.labels[ch]['e'] = label

        frame = tk.Frame(self._gui, bg='#999999')
        frame.pack()
        frame.place(in_=top, relx=0.5, rely=2.0, relwidth=0.8, relheight=0.25, anchor='center')
        self.popup_frame = frame
        label = tk.Label(self._gui, text="", font=('Verdana', 26), bg='#999999', fg='#ffffff', anchor='center')
        label.pack(in_=self.popup_frame, fill=tkinter.BOTH, expand=True)
        self.popup_label = label
        self.popup_hide_timeout = None

        if AppConfig._debug:
            label = tk.Label(self._gui, text="", font=('Verdana', 12), bg='#333333', fg=self.TEXT_COLOR, anchor='nw', wraplength=800)
            label.pack()
            label.place(in_=top, relx=0.0, rely=1.0-0.135 + 2.0, relwidth=1.0, relheight=0.13)
            self.debug_label = label
            self.debug_label_state = 2
        try:
            with open(AppConfig.get_filename(self.get_gui_scheme_config_filename(True)), 'w') as f:
                f.write(json.dumps(gui, indent=2))
        except Exception as e:
            self.debug(__name__, 'failed to write GUI config: %s', e)


        self._gui.init_bindings()


    def destroy(self):
        MainAppCli.destroy(self)
        self._gui.destroy()

    def mainloop(self):
        self.debug(__name__, 'mainloop gui=%s' % (self._gui and 'enabled' or 'disabled'))
        if self._gui:
            self._gui.mainloop()
        else:
            MainAppCli.loop(self, False)

    def quit(self):
        MainAppCli.quit(self)
        if self._gui:
            self._gui.quit()

    def init_scheme(self):
        if not self.desktop:
            self.geometry_info = (128, 64, 2.0)
        else:
            self.geometry_info = (800, 480, 1.0)

        self._gui.geometry("%ux%u" % (self.geometry_info[0], self.geometry_info[1]))
        self._gui.tk.call('tk', 'scaling', self.geometry_info[2])

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
            self.debug(__name__, 'animation_set_state pause=%s interval=%u set=%s is_running=%s' % (pause, self.ani_interval, str(interval), is_running))
            if pause:
                if is_running:
                    self.debug(__name__, 'stopping animation')
                    self.ani.event_source.stop()
                self.ani.event_source.interval = ANIMATION.PAUSED
            else:
                if interval!=None:
                    self.ani_interval = interval
                self.ani.event_source.interval = self.ani_interval
                if not is_running:
                    self.debug(__name__, 'starting animation')
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
            self.debug(__name__, 'changing animation update rate: %u (paused)' % rate)
            self.ani_interval = rate
            return

        if not self.animation_compare_interval(rate):
            self.debug(__name__, 'changing animation update rate: %u' % rate)
            self.animation_set_state(False, rate)
        # else:
            # self.debug(__name__, 'animation update rate already set: %u' % rate)

    def get_gui_scheme_config_filename(self, auto=''):
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
        self.debug(__name__, 'reload gui')
        try:
            with open(AppConfig.get_filename(self.get_gui_scheme_config_filename()), 'r') as f:
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
            self.error(__name__, 'reloading GUI failed: %s' % e)
        return "break"

    def reload_config(self, event=None):
        self.debug(__name__, 'reload config')
        try:
            ConfigLoader.ConfigLoader.load_config()
        except Exception as e:
            self.error(__name__, 'reloading configuration failed: %s' % e)
        return "break"

    def button_1(self, event):

        x = int(event.x / (self.geometry_info[0] / 8))
        y = int(event.y / (self.geometry_info[1] / 4))

        self.debug(__name__, 'button1 %u:%u %.2fx%.2f' % (x, y, self.geometry_info[0] / 8, self.geometry_info[1] / 4))

        if x<=1 and y==0:
            self.toggle_time_scale(-1)
        elif x>=6 and y==0:
            self.toggle_time_scale(+1)
        elif x<3:
            self.toggle_plot_visibility()
        else:
            self.toggle_primary_display()

    def toggle_time_scale(self, event=None):
        num = len(self._time_scale_items)
        if event==-1 or event==1:
            pass
        elif event==None:
            event = 1
        self._gui_config.plot_time_scale = self._gui_config.plot_time_scale + 0.10 * event
        self._gui_config.plot_time_scale = min(1.0, max(0.0, self._gui_config.plot_time_scale))
        self.legend();
        self.show_popup('%u of %u seconds (%.1f%%)' % (self.get_time_scale(), AppConfig.plot.max_time, self._gui_config.plot_time_scale * 100))
        return "break"

    def store_values(self, event=None):
        fn = 'data-%u.json' % int(time.monotonic())
        self.debug(__name__, 'stored values in %s' % fn)
        with open(fn, 'w') as f:
            f.write(json.dumps(self.values, indent=2))
        return "break"

    def debug_bind(self, event=None):
        # x = int(event.x / (self.geometry_info[0] / 6))
        # y = int(event.y / (self.geometry_info[1] / 3))
        # self.debug(__name__, '%d %d %s' % (x,y,str(event)))
        self.debug(__name__, event)
        return "break"

    def toggle_animation(self, event=None):
        self.debug(__name__, 'toggle_animation running=%s' % self.animation_is_running())
        self.animation_set_state(pause=self.animation_is_running())
        return 'break'

    def toggle_plot_visibility(self, event=None):
        self._gui_config.plot_visibility = Tools.EnumIncr(self._gui_config.plot_visibility)
        idx = 0
        for ax in self.ax:
            n = self.get_plot_geometry(idx)
            self.debug(__main__, 'idx=%u v=%s get_plot_geometry=%s', idx, str(self._gui_config.plot_visibility), s)
            if n!=None:
                ax.set_visible(True)
                ax.change_geometry(int(n / 100) % 10, int(n / 10) % 10, int(n) % 10)
            elif ax:
                ax.set_visible(False)
            idx += 1
        self.canvas.draw()
        return 'break'

    def toggle_primary_display(self, event=None):
        self._gui_config.plot_primary_display = Tools.EnumIncr(self._gui_config.plot_primary_display)
        self.set_main_plot()
        return 'break'

    def toggle_display_energy(self, event=None):
        self._gui_config.plot_display_energy = Tools.EnumIncr(self._gui_config.plot_display_energy)
        return 'break'

    def show_popup(self, msg, timeout=3.5):
        if msg==None:
            self.popup_hide_timeout = None
            self.popup_frame.place(rely=2.0)
        else:
            self.popup_hide_timeout = time.monotonic() + timeout
            self.popup_label.configure(text=msg)
            self.popup_frame.place(rely=0.28)


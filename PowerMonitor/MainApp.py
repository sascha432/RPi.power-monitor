#
# Author: sascha_lammers@gmx.de
#

from . import *
from Config.Type import Type
from .AppConfig import Channel
from .Enums import COLOR_SCHEME
import SDL_Pi_INA3221
from SDL_Pi_INA3221.Calibration import Calibration
from collections import namedtuple
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
        return tmp

class MainAppCli(Plot.Plot):
    def __init__(self):
        self.fullscreen_state = False

    def start(self):
        self.debug(__name__, 'start')

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
        # self.lines = [ [], [] ] # lines for ax[0], ax[1]

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
        self.debug(__name__, 'reset values')
        self.lock.acquire()
        try:
            self.reset_data()
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

        for func_name in ('start', 'destroy', 'reload', 'init_vars'):
            obj = Tools.LambdaCaller(Tools.execute_method, (self, self._bases, func_name))
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
        e = ''
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

    def import_tkinter(self):
        global Gui, tk, ttk, font, tkinter, animation, Figure, FigureCanvasTkAgg, NavigationToolbar2Tk
        # import matplotlib
        # matplotlib.use('tkagg')
        from .Gui import Gui
        import tkinter
        from tkinter import font
        import tkinter as tk
        from tkinter import ttk
        import tkinter.messagebox
        import matplotlib.animation as animation
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
        return (Gui, tk, ttk, font, tkinter, animation, Figure, FigureCanvasTkAgg, NavigationToolbar2Tk)

    def __init_gui__(self):

        self.debug(__name__, 'starting with GUI')
        self.import_tkinter()

        self.read_gui_config()
        self._gui = Gui(self)

        # color scheme and screen size
        self.init_scheme()
        self.init_plot()

        self._gui.init_bindings()
        self._gui.bind('<F6>', self.debugf6)

    def debugf6(self, event=None):
        # self.plot_values(-1)
        self.canvas.draw()
        # self.canvas.flush_events()


    def window_resize(self):
        pass
        # if self._gui.fullscreen_state:
        #     self._geometry_info = (800, 480, 1.0)#TODO get real size
        # else:
        #     tmp = AppConfig.gui.geometry.split('x')
        #     self._geometry_info = (int(tmp[0]), int(tmp[1]), float(tmp[2]))

        # self.debug_label.configure(wraplength=self._geometry_info[0])
        # self._fonts.top_font.configure(size=int(self._fonts.top_font._org_size * self._geometry_info[2]))
        # self._fonts.plot_font.configure(size=int(self._fonts.plot_font._org_size * self._geometry_info[2]))
        # self._fonts.debug_font.configure(size=int(self._fonts.debug_font._org_size * self._geometry_info[2]))
        # self._fonts.label_font.configure(size=int(self._fonts.label_font._org_size * self._geometry_info[2]))

        # for ax in self.ax:
        #     ax.tick_params(labelsize=self._fonts.plot_font.cget('size'))
        # self.legend()



    def destroy(self):
        if self.ani:
            self.debug(__name__, 'stop animation')
            self.ani.event_source.stop()
        self._gui.destroy()

    # def ani_callback(self, i=None):
    #     self.debug(__name__, 'animation callback %u', i)

    def ani_start(self):
        self.ani_interval = AppConfig.plot.refresh_interval
        self.debug(__name__, 'start animation %u', self.ani_interval)
        self.lock.acquire()
        try:
            self.ani = animation.FuncAnimation(self.fig, self.plot_values, interval=self.ani_interval, blit=True)
            self.canvas.draw_idle()
        except:
            AppConfig._debug_exception(e)

        finally:
            self.lock.release()


    def ani_schedule_start(self, time=0.01):
        self._scheduler.enter(time, 100, self.ani_start)

    def ani_get_speed_type(self):
        return self.ani_interval==AppConfig.plot.refresh_interval

    def ani_get_speed(self, fast=True):
        if fast:
            return AppConfig.plot.refresh_interval
        return AppConfig.plot.idle_refresh_interval

    def ani_update(self):
        self.lock.acquire()
        try:
            self.ani.event_source.stop()
            self.canvas.draw()
            self.canvas.flush_events()
            self.ani = None
            self.ani_schedule_start()
            # self.ani.event_source.start()
        finally:
            self.lock.release()

    def ani_toggle_speed(self, event=None):
        self.debug(__name__, 'toggle animation speed %u', self.ani_interval)
        if not self.ani:
            self.error(__name__, 'animation not running')
            return
        self.lock.acquire()
        try:
            if self.ani_interval==AppConfig.plot.refresh_interval:
                self.ani_interval = AppConfig.plot.idle_refresh_interval
            else:
                self.ani_interval = AppConfig.plot.refresh_interval
            self.debug(__name__, 'animation interval %u' % self.ani_interval)
            self.ani.event_source.stop()
            self.ani.event_source.interval = self.ani_interval
            self.ani.event_source.start()
        finally:
            self.lock.release()

        return "break"

    def mainloop(self):
        self.debug(__name__, 'mainloop gui=%s' % (self._gui and 'enabled' or 'disabled'))
        if self._gui:
            self._gui.mainloop()
        else:
            MainAppCli.loop(self, False)

    def quit(self):
        if self._gui:
            self._gui.quit()

    def init_scheme(self):

        tmp = AppConfig.gui.geometry.split('x')
        self._geometry_info = (int(tmp[0]), int(tmp[1]), float(tmp[2]))
        self._gui.geometry("%ux%u" % (self._geometry_info[0], self._geometry_info[1]))
        self._gui.tk.call('tk', 'scaling', self._geometry_info[2])

        if AppConfig.gui.color_scheme == COLOR_SCHEME.DARK:
            self.BG_COLOR = 'black'
            self.TEXT_COLOR = 'white'
            self.PLOT_TEXT = self.TEXT_COLOR
            self.PLOT_GRID = 'gray'
            self.PLOT_BG = "#303030"
            self.FG_CHANNEL0 = 'red'
            self.FG_CHANNEL1 = 'lime'
            self.FG_CHANNEL2 = 'deepskyblue'
            self.FG_CHANNEL3 = '#b4b0d1' # 'lavender'
        elif AppConfig.gui.color_scheme == COLOR_SCHEME.LIGHT:
            self.FG_CHANNEL0 = 'red'
            self.FG_CHANNEL1 = 'green'
            self.FG_CHANNEL2 = 'blue'
            self.FG_CHANNEL3 = 'aqua'
            self.BG_COLOR = 'white'
            self.TEXT_COLOR = 'black'
            self.PLOT_TEXT = self.TEXT_COLOR
            self.PLOT_GRID = 'black'
            self.PLOT_BG = "#f0f0f0"
        else:
            raise ValueError('invalid color scheme')

        Channel.COLOR_AGGREGATED_POWED = self.FG_CHANNEL0
        AppConfig.channels[0].color = self.FG_CHANNEL1
        AppConfig.channels[1].color = self.FG_CHANNEL2
        AppConfig.channels[2].color = self.FG_CHANNEL3


        self._fonts = namedtuple('GuiFonts', ['top_font', 'plot_font', 'debug_font', 'label_font'])
        self._fonts.top_font = font.Font(family='Helvetica', size=20)
        self._fonts.plot_font = font.Font(family='Helvetica', size=8)
        self._fonts.debug_font = font.Font(family='Helvetica', size=10)
        label_font_size = (32, 28, 18)
        self._fonts.label_font = font.Font(family='Helvetica', size=label_font_size[len(self.channels) - 1])

        for name in self._fonts._fields:
            tmp = getattr(self._fonts, name)
            setattr(tmp, '_org_size', tmp.cget('size'))

        self.TOP_FONT = "DejaVu Sans"
        self.TOP_PADDING = (2, 20)
        self.PLOT_DPI = 200
        self.LABELS_PADX = 10

    def set_screen_update_rate(self, fast=True):
        if self.ani_get_speed_type()==fast:
            self.ani_toggle_speed()

    def get_gui_scheme_config_filename(self, auto=''):
        if auto==True:
            auto = '-auto'
        return 'gui-%u-%ux%u%s.json' % (len(self.channels), self._geometry_info[0], self._geometry_info[1], auto)
        # self._geometry_info[1], auto)

    def toggle_debug(self, event=None):
        self.debug_label_state = (self.debug_label_state + 1) % 3
        if self.debug_label_state==0:
            self.debug_label.place(rely=1.0-0.135, relheight=0.13)
            self._fonts.debug_font.configure(size=10)
            self.debug_label.configure(font=self._fonts.debug_font)
            # self.debug_label.configure(font=('Verdana', 10))
        if self.debug_label_state==1:
            self.debug_label.place(rely=1.0-0.255, relheight=0.25)
            # self.debug_label.configure(font=('Verdana', 18))
            self._fonts.debug_font.configure(size=18)
            self.debug_label.configure(font=self._fonts.debug_font)
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

            self.ani_update()

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

        x = int(event.x / (self._geometry_info[0] / 8))
        y = int(event.y / (self._geometry_info[1] / 4))

        self.debug(__name__, 'button1 %u:%u %.2fx%.2f' % (x, y, self._geometry_info[0] / 8, self._geometry_info[1] / 4))

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
        self.ani_update()
        self.show_popup('%u of %u seconds (%.1f%%)' % (self.get_time_scale(), AppConfig.plot.max_time, self._gui_config.plot_time_scale * 100))
        # self.change_averaging_mode(self.get_time_scale())
        return "break"

    def store_values(self, event=None):
        fn = 'data-%u.json' % int(time.monotonic())
        self.debug(__name__, 'stored values in %s' % fn)
        with open(fn, 'w') as f:
            f.write(json.dumps(self.values, indent=2))
        return "break"

    def debug_bind(self, event=None):
        # x = int(event.x / (self._geometry_info[0] / 6))
        # y = int(event.y / (self._geometry_info[1] / 3))
        # self.debug(__name__, '%d %d %s' % (x,y,str(event)))
        self.debug(__name__, event)
        return "break"

    def toggle_plot_visibility(self, event=None):
        self._gui_config.plot_visibility = Tools.EnumIncr(self._gui_config.plot_visibility)
        self.set_plot_geometry()
        self.ani_update()
        return 'break'

    def set_plot_geometry(self):
        idx = 0
        for data in self._ax_data:
            ax = data.ax
            n = self.get_plot_geometry(idx)
            self.debug(__name__, 'idx=%u visibility=%s get_plot_geometry=%s', idx, str(self._gui_config.plot_visibility), n)
            if n!=None:
                ax.set_visible(True)
                ax.change_geometry(int(n / 100) % 10, int(n / 10) % 10, int(n) % 10)
            elif ax:
                ax.set_visible(False)
            idx += 1

    def toggle_primary_display(self, event=None):
        self._gui_config.plot_primary_display = Tools.EnumIncr(self._gui_config.plot_primary_display)
        self.set_main_plot()
        self.ani_update()
        return 'break'

    def toggle_display_energy(self, event=None):
        self._gui_config.plot_display_energy = Tools.EnumIncr(self._gui_config.plot_display_energy)
        self.ani_update()
        return 'break'

    def show_popup(self, msg, timeout=3.5):
        if msg==None:
            self.popup_hide_timeout = None
            self.popup_frame.place(rely=2.0)
        else:
            self.popup_hide_timeout = time.monotonic() + timeout
            self.popup_label.configure(text=msg)
            self.popup_frame.place(rely=0.28)


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

class NamedTuples:
    YLimit = namedtuple('YLimit', ('min', 'max', 'ts'))

class GuiConfig(object):

    def __init__(self, parent=None, data={}, allowed=None, exception=False):
        object.__setattr__(self, '_parent', parent)
        object.__setattr__(self, '_allowed', allowed)
        object.__setattr__(self, '_exception', exception)
        object.__setattr__(self, '_disabled', True)
        for key, val in data.items():
            object.__setattr__(self, key, val)
        if allowed:
            for key in allowed:
                if not hasattr(self, key):
                    object.__setattr__(self, key, data[key])

    @property
    def disabled(self):
        return self._disabled==False

    @disabled.setter
    def disabled(self, value):
        object.__setattr__(self, '_disabled', value)

    def __setattr__(self, key, val):
        if self._disabled==False and not key.startswith('_'):
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

    def assign_attrs(self, child):
        # setattr(child, 'debug', self.debug)
        # setattr(child, 'info', self.info)
        # setattr(child, 'warning', self.warning)
        name = '%s.%s' % (child.__module__, child.__class__.__qualname__)
        setattr(child, 'debug', lambda *args: self.debug(name, *args))
        setattr(child, 'info', lambda *args: self.info(name, *args))
        setattr(child, 'warning', lambda *args: self.warning(name, *args))
        setattr(child, 'error', lambda *args: self.error(name, *args))

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


    def y_limit_clear(self, axis):
        self._y_limits[axis] = NamedTuples.YLimit(min=sys.maxsize, max=0, ts=0)

    def y_limit_update(self, axis, min, max):
        self._y_limits[axis] = NamedTuples.YLimit(min=min, max=max, ts=time.monotonic())

    def _y_limit_has_changed(self, axis, min, max):
        res = self._y_limit_has_changed(axis, min, max)
        print('y_limit_has_changed',axis,min,max,res)
        return res

    def y_limit_has_changed(self, axis, min, max, timeout=5, round_digits=2, tolerance=0.01):
        li = self._y_limits[axis]
        return (li.ts == 0) or \
            (round(min + tolerance, round_digits) < round(li.min, round_digits)) or \
            (round(max - tolerance, round_digits) > round(li.max, round_digits)) or \
                ((time.monotonic() + timeout >= li.ts) and (round(min, round_digits) != round(li.min, round_digits) or round(max, round_digits) != round(li.max, round_digits)))


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
        if not self._data_lock.acquire(True, 5.0):
            self.error(__name__, 'reset_values could not acquire lock')
            return
        try:
            self.reset_data()
            self.stats = {}
            self.start_time = time.monotonic()
            self.compressed_ts = -1
            self.compressed_min_records = 0
            self.plot_updated = 0
            self.plot_updated_times = []
            self._y_limits = [[]]*4
            for i in range(0, len(self._y_limits)):
                self.y_limit_clear(i)
            self.power_sum = [ 1 ]
            self.values = PlotValuesContainer(self.channels)
            if self._animation.active:
                self._animation.reset()
        finally:
            self._data_lock.release()

    def reset_plot(self):
        try:
            self.ani.event_source.stop()
            self.ani = None
        except:
            self.ani = None
        self.reset_values()
        self.reset_data()

    def reset_energy(self):
        self.energy = dict(enumerate([{'t': 0, 'ei': 0, 'ep': 0}]*3))
        self.energy['stored'] = 0

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

    def mainloop(self):
        self.debug(__name__, 'mainloop gui=%s' % (self._gui and 'enabled' or 'disabled'))
        if self._gui:
            self._gui.mainloop()
        else:
            MainAppCli.loop(self, False)

    def quit(self):
        if self._gui:
            self._gui.quit()

    def _execute_base_methods(self_obj, func_name, *args, **kwargs):
        self_obj.debug(__name__, 'calling __bases__.%s', func_name)
        Tools.execute_method(self_obj, self_obj._bases, func_name, *args, **kwargs)

    def import_tkinter(self):
        from .Gui import Gui
        import tkinter
        from tkinter import font, ttk
        #import tkinter as tk
        # from tkinter import ttk
        import tkinter.messagebox
        # from matplotlib.animation import FuncAnimation
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        return {
            'Gui': Gui,
            'tk': tkinter,
            'ttk': ttk,
            'font': font,
            'tkinter': tkinter,
            # 'FuncAnimation': FuncAnimation,
            'Figure': Figure,
            'FigureCanvasTkAgg': FigureCanvasTkAgg
        }

    def __init_gui__(self):

        self.debug(__name__, 'starting with GUI')
        globals().update(self.import_tkinter())

        self.read_gui_config()
        self._gui = Gui(self)

        # color scheme and screen size
        self.init_scheme()
        self.init_plot()

        self._gui.init_bindings()
        self._gui.bind('<F6>', self.debugf6)

    def debugf6(self, event=None):
        for data in self._ax_data:
            print(type(data.ax.get_children()))
            print(data.ax.get_children())

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

        # for data in self._ax_data:
        #     data.ax.tick_params(labelsize=self._fonts.plot_font.cget('size'))
        # self.add_ticks()


    def destroy(self):
        if self.ani:
            self.debug(__name__, 'stop animation')
            self.ani.event_source.stop()
        self._gui.destroy()

    def init_scheme(self):

        tmp = AppConfig.gui.geometry.split('x')
        self._geometry_info = (int(tmp[0]), int(tmp[1]), float(tmp[2]))
        self._gui.geometry("%ux%u" % (self._geometry_info[0], self._geometry_info[1]))
        self._gui.tk.call('tk', 'scaling', self._geometry_info[2])

        if AppConfig.gui.color_scheme == COLOR_SCHEME.DARK:
            self.CHANNELS = ['lime', 'deepskyblue', '#b4b0d1', '#0e830e', '#8681b5', '#268daf', 'red']
            self.BG_COLOR = 'black'
            self.TEXT_COLOR = 'white'
            self.PLOT_TEXT = self.TEXT_COLOR
            self.PLOT_GRID = 'gray'
            self.PLOT_BG = "#303030"
        elif AppConfig.gui.color_scheme == COLOR_SCHEME.LIGHT:
            self.CHANNELS = ['green', 'blue', 'aqua', 'green', 'blue', 'aqua', 'red']
            self.BG_COLOR = 'white'
            self.TEXT_COLOR = 'black'
            self.PLOT_TEXT = self.TEXT_COLOR
            self.PLOT_GRID = 'black'
            self.PLOT_BG = "#f0f0f0"
        else:
            raise ValueError('invalid color scheme')

        Channel.COLOR_AGGREGATED_POWER = self.CHANNELS[6]

        for i in range(3):
            if AppConfig.channels[i].color=='':
                AppConfig.channels[i].color = self.CHANNELS[i]
            if AppConfig.channels[i].hline_color=='':
                AppConfig.channels[i].hline_color = self.CHANNELS[i + 3]


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

    def set_screen_update_rate(self, running=True):
        if (self._animation.mode!=Animation.Mode.RUNNING)==running:
            self.mode = Animation.Mode.IDLE

    def get_gui_scheme_config_filename(self, auto=''):
        if auto==True:
            auto = '-auto'
        return 'gui-%u-%ux%u%s.json' % (len(self.channels), self._geometry_info[0], self._geometry_info[1], auto)
        # self._geometry_info[1], auto)

    # ---------------------------------------------------------------------------------------------
    # gui config
    # ---------------------------------------------------------------------------------------------

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

        self._gui_config.disabled = False


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

    # ---------------------------------------------------------------------------------------------
    # tk events
    # ---------------------------------------------------------------------------------------------

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

            self._animation.update()

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
        self.add_ticks()
        self._animation.update()
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
        self.debug(__name__, 'visibility %s', str(self._gui_config.plot_visibility))
        self.set_plot_geometry()
        self.reconfigure_axis()
        self._animation.update()
        return 'break'

    def toggle_primary_display(self, event=None):
        self._gui_config.plot_primary_display = Tools.EnumIncr(self._gui_config.plot_primary_display)
        self.reconfigure_axis()
        self._animation.update()
        return 'break'

    def toggle_display_energy(self, event=None):
        self._gui_config.plot_display_energy = Tools.EnumIncr(self._gui_config.plot_display_energy)
        self._animation.update()
        return 'break'

    def show_popup(self, msg, timeout=3.5):
        if msg==None:
            self.popup_hide_timeout = None
            self.popup_frame.place(rely=2.0)
        else:
            self.popup_hide_timeout = time.monotonic() + timeout
            self.popup_label.configure(text=msg)
            self.popup_frame.place(rely=0.28)


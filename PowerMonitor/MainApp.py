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

class MainApp(Plot.Plot):

    def __init__(self, logger, app_config):
        global AppConfig
        AppConfig = app_config

        self._gui = None
        self._logger = logger
        self._app_config = app_config
        self._bases = Tools.get_bases(self.__module__, self.__class__.__qualname__)
        self.fullscreen_state = False

        for func_name in ('start', 'destroy', 'reload', 'init_vars'):
            obj = Tools.LambdaCaller(Tools.execute_method, (self, self._bases, func_name))
            setattr(self, func_name, obj)

        for class_type in self._bases:
            self.debug(__name__, '%s.__init__()', class_type)
            class_type.__init__(self)

        self.main_init_vars()
        self.init_vars()

        try:
            if not AppConfig.headless:
                self.__init_gui__()
        except Exception as e:
            self._gui = None
            if not AppConfig.headless:
                self.error(__name__, 'failed to initialize GUI: %s', e)
            self.debug(__name__, 'starting headless')
            AppConfig._debug_exception(e)

        self.start()


    def assign_attrs(self, child):
        # setattr(child, 'debug', self.debug)
        # setattr(child, 'info', self.info)
        # setattr(child, 'warning', self.warning)
        name = '%s.%s' % (child.__module__, child.__class__.__qualname__)
        setattr(child, 'debug', lambda *args: self.debug(name, *args))
        setattr(child, 'info', lambda *args: self.info(name, *args))
        setattr(child, 'warning', lambda *args: self.warning(name, *args))
        setattr(child, 'error', lambda *args: self.error(name, *args))

    def mainloop(self):
        self.debug(__name__, 'mainloop gui=%s' % (self._gui and 'enabled' or 'disabled'))
        if self._gui:
            self._gui.mainloop()

    def main_init_vars(self):

        self.debug(__name__, 'init_vars')
        self._gui_config = None
        # channels to display
        self.channels = Channels()
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
        self.reset_energy()
        self.reset_data()

    def quit(self):
        if self._gui:
            self._gui.quit()

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

    def add_stats(self, name, value, set_value=False):
        if set_value:
            self.stats = value
            return
        if not name in self.stats:
            self.stats[name] = 0
        self.stats[name] += value

    def reset_values(self, lock=True):
        self.debug(__name__, 'reset values')
        if lock and not self._data_lock.acquire(True, 5.0):
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
            if lock:
                self._data_lock.release()

    @staticmethod
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

    @property
    def geometry(self):
        return self._gui._geometry_info

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
        return "break"

    def destroy(self):
        self.remove_scheduled_gui_writes()
        self._write_gui_config()
        if self.ani:
            self.debug(__name__, 'stop animation')
            self.ani.event_source.stop()
        self._gui.destroy()

    def init_scheme(self):

        tmp = AppConfig.gui.geometry.split('x', 3)
        self._gui.geometry(*tmp)

        if AppConfig.gui.color_scheme == COLOR_SCHEME.DARK:
            self.CHANNELS = ['lime', 'deepskyblue', '#b4b0d1', '#0e830e', '#8681b5', '#268daf', 'red']
            self.BG_COLOR = 'black'
            self.TEXT_COLOR = 'white'
            self.PLOT_TEXT = self.TEXT_COLOR
            self.PLOT_GRID = 'gray'
            self.PLOT_BG = "#303030"
            self.POPUP_TEXT = 'white'
            self.POPUP_BG_COLOR = '#999999'
        elif AppConfig.gui.color_scheme == COLOR_SCHEME.LIGHT:
            self.CHANNELS = ['green', 'blue', 'aqua', 'green', 'blue', 'aqua', 'red']
            self.BG_COLOR = 'white'
            self.TEXT_COLOR = 'black'
            self.PLOT_TEXT = self.TEXT_COLOR
            self.PLOT_GRID = 'black'
            self.PLOT_BG = "#f0f0f0"
            self.POPUP_TEXT = 'black'
            self.POPUP_BG_COLOR = '#303030'
        else:
            raise ValueError('invalid color scheme')

        Channel.COLOR_AGGREGATED_POWER = self.CHANNELS[6]

        for i in range(3):
            if not AppConfig.channels[i].color:
                AppConfig.channels[i].color = self.CHANNELS[i]
            if not AppConfig.channels[i].hline_color:
                AppConfig.channels[i].hline_color = self.CHANNELS[i + 3]

        self._fonts = namedtuple('GuiFonts', ['top_font', 'debug_font', 'label_font'])
        self._fonts.top_font = font.Font(family='Helvetica', size=20)
        self._fonts.debug_font = font.Font(family='Helvetica', size=10)
        label_font_size = (32, 28, 22)
        self._fonts.label_font = font.Font(family='Helvetica', size=label_font_size[len(self.channels) - 1])

    def set_screen_update_rate(self, running=True):
        if (self._animation.mode!=Animation.Mode.RUNNING)==running:
            self.mode = Animation.Mode.IDLE

    # def get_gui_scheme_config_filename(self, auto=''):
    #     if auto==True:
    #         auto = '-auto'
    #     return 'gui-%u-%ux%ux%s%s.json' % (len(self.channels), self.geometry.width, self.geometry.height, self.geometry.scaling, auto)

    # ---------------------------------------------------------------------------------------------
    # gui config
    # ---------------------------------------------------------------------------------------------

    def read_gui_config(self):
        defaults = GuiConfig.DEFAULTS
        e = ''
        try:
            file = AppConfig.get_filename('config_state.json')
            self.debug(__name__, 'read gui config %s', file)
            with open(file, 'r') as f:
                data = json.loads(f.read())
                self._gui_config = GuiConfig(self, data)
        except Exception as e:
            self.info(__name__, 'failed to load: %s: %s', file, e)
            self._gui_config = GuiConfig(self, defaults)

        try:
            self._gui_config.plot_visibility = Tools.EnumFromStr(PLOT_VISIBILITY, self._gui_config.plot_visibility)
            self._gui_config.plot_display_energy = Tools.EnumFromStr(DISPLAY_ENERGY, self._gui_config.plot_display_energy)
            self._gui_config.plot_primary_display = Tools.EnumFromStr(PLOT_PRIMARY_DISPLAY, self._gui_config.plot_primary_display)
            self._gui_config.plot_time_scale = max(0, min(1, float(self._gui_config.plot_time_scale)))
            self._gui_config.plot_channels = int(self._gui_config.plot_channels)
        except Exception as e:
            self.info(__name__, 'invalid configuration: %s: %s', file, e)
            self._gui_config = GuiConfig(self, defaults)

        self.debug(__name__, 'gui configuration %s' % json.dumps(self._gui_config._asdict(), indent=2))

        self._gui_config.disabled = False


    def _write_gui_config(self):
        try:
            file = AppConfig.get_filename('config_state.json')
            self.debug(__name__, 'write gui config %s', file)
            with open(file, 'w') as f:
                f.write(json.dumps(self._gui_config._asdict()))
        except Exception as e:
            self.error(__name__, 'failed to store: %s: %s', file, e)

    def remove_scheduled_gui_writes(self):
        for item in self._scheduler.queue:
            if getattr(item, 'priority')==SCHEDULER_PRIO.WRITE_GUI_CONFIG:
                self._scheduler.cancel(item)

    def write_gui_config(self):
        self.remove_scheduled_gui_writes()
        self._scheduler.enter(10.0, SCHEDULER_PRIO.WRITE_GUI_CONFIG, self._write_gui_config)

    # ---------------------------------------------------------------------------------------------
    # tk events
    # ---------------------------------------------------------------------------------------------

    def reset_plot(self):
        self._animation.end()
        self.reset_values()
        self.reset_data()
        self.reconfigure_axis()
        self.canvas.redraw()
        self._animation.restart()
        return "break"

    def toggle_debug(self, event=None):
        self.debug_label_state = (self.debug_label_state + 1) % 3
        if self.debug_label_state==0:
            self.debug_label.place(rely=1.0-0.135, relwidth=1.0, relheight=0.13)
            self._fonts.debug_font.configure(size=10)
            self.debug_label.configure(font=self._fonts.debug_font)
            # self.debug_label.configure(font=('Verdana', 10))
        if self.debug_label_state==1:
            self.debug_label.place(rely=1.0-0.255, relwidth=1.0, relheight=0.25)
            # self.debug_label.configure(font=('Verdana', 18))
            self._fonts.debug_font.configure(size=18)
            self.debug_label.configure(font=self._fonts.debug_font)
        if self.debug_label_state==2:
            self.debug_label.place(relx=0, rely=0, relwidth=0, relheight=0)
        return 'break'

    # def reload_gui(self, event=None):
    #     self.debug(__name__, 'reload gui')
    #     try:
    #         with open(AppConfig.get_filename(self.get_gui_scheme_config_filename()), 'r') as f:
    #             gui = json.loads(f.read())
    #         self.canvas.get_tk_widget().place(**gui['plot_placement'])
    #         places = gui['label_places']
    #         for channel in self.channels:
    #             if channel.enabled:
    #                 self.labels[channel]['U'].place(**places.pop(0))
    #                 self.labels[channel]['I'].place(**places.pop(0))
    #                 self.labels[channel]['P'].place(**places.pop(0))
    #                 self.labels[channel]['e'].place(**places.pop(0))

    #         self._animation.update()

    #     except Exception as e:
    #         self.error(__name__, 'reloading GUI failed: %s' % e)
    #     return "break"

    def reload_config(self, event=None):
        self.debug(__name__, 'reload config')
        try:
            ConfigLoader.ConfigLoader.load_config()
        except Exception as e:
            self.error(__name__, 'reloading configuration failed: %s' % e)
        return "break"

    def button_1(self, event):

        x = int(event.x / (self.geometry.width / 8))
        y = int(event.y / (self.geometry.height / 4))

        self.debug(__name__, 'button1 %u:%u %.2fx%.2f' % (x, y, self.geometry.width / 8, self.geometry.height / 4))

        if x<=1 and y==0:
            self.toggle_time_scale(-1)
        elif x>=6 and y==0:
            self.toggle_time_scale(+1)
        elif x<3:
            self.toggle_plot_visibility()
        else:
            self.toggle_primary_display()

    def toggle_time_scale(self, event=None):
        self._animation.end()
        num = len(self._time_scale_items)
        if event==-1 or event==1:
            pass
        elif event==None:
            event = 1
        self._gui_config.plot_time_scale = self._gui_config.plot_time_scale + 0.10 * event
        self._gui_config.plot_time_scale = min(1.0, max(0.0, self._gui_config.plot_time_scale))
        self.reconfigure_axis()
        self.canvas.draw()
        self._animation.restart()
        self.show_popup('%u of %u seconds (%.1f%%)' % (self.get_time_scale(), AppConfig.plot.max_time, self._gui_config.plot_time_scale * 100))
        # self.change_averaging_mode(self.get_time_scale())
        return "break"

    def toggle_channel(self, channel, event=None):
        self._animation.end()

        bv = (1 << channel)
        if self._gui_config.plot_channels & bv:
            self._gui_config.plot_channels &= ~bv
        else:
            self._gui_config.plot_channels |= bv

        # self.debug(__name__, 'displayed channels %s ' % self._gui_config.plot_channels)
        self.debug(__name__, 'active channels: %s' % ([channel.name for channel in self.active_channels]))

        # self.reinit_main_frame()
        self.set_plot_geometry()
        self.reconfigure_axis()
        self.canvas.draw()
        self._animation.restart()
        return "break"


    def store_values(self, event=None):
        fn = 'data-%u.json' % int(time.monotonic())
        self.debug(__name__, 'stored values in %s' % fn)
        with open(fn, 'w') as f:
            f.write(json.dumps(self.values, indent=2))
        return "break"

    def debug_bind(self, event=None):
        # x = int(event.x / (self.geometry.width / 6))
        # y = int(event.y / (self.geometry.height / 3))
        # self.debug(__name__, '%d %d %s' % (x,y,str(event)))
        self.debug(__name__, event)
        return "break"

    def toggle_plot_visibility(self, event=None):
        self._animation.end()
        self._gui_config.plot_visibility = Tools.EnumIncr(self._gui_config.plot_visibility)
        self.debug(__name__, 'visibility %s', str(self._gui_config.plot_visibility))
        self.set_plot_geometry()
        self.reconfigure_axis()
        self.canvas.draw()
        self._animation.restart()
        return 'break'

    def toggle_primary_display(self, event=None):
        self._animation.end()
        self._gui_config.plot_primary_display = Tools.EnumIncr(self._gui_config.plot_primary_display)
        self.reconfigure_axis()
        self.canvas.draw()
        self._animation.restart()
        return 'break'

    def toggle_display_energy(self, event=None):
        self._animation.end()
        self._gui_config.plot_display_energy = Tools.EnumIncr(self._gui_config.plot_display_energy)
        self.reconfigure_axis()
        self.canvas.draw()
        self._animation.restart()
        return 'break'

    def show_popup(self, msg, timeout=3.5):
        self.debug(__name__, 'show_popup: %s: %s', str(timeout), msg)
        if msg==None:
            self.popup_hide_timeout = None
            self.popup_frame.pack_forget()
            self.popup_frame.place(relx=0, rely=0, relwidth=0, relheight=0)
        else:
            self.popup_hide_timeout = time.monotonic() + timeout
            self.popup_label.configure(text=msg)
            self.popup_frame.pack()
            self.popup_frame.place(**self._popup_placement)

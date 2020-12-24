#
# Author: sascha_lammers@gmx.de
#

import tkinter as tk
import traceback
import sys
import copy
from . import Enums, Tools
from Config import Param, EnumConverter

class Geometry(object):

    DEFAULT_DPI = 72

    def __init__(self):
        self._width = 0
        self._height = 0
        self._scaling = None
        self._dpi = None

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def dpi(self):
        if self._dpi==None:
            return round(Geometry.DEFAULT_DPI * self.scaling)
        if self._dpi<0:
            return round(-self._dpi)
        return round(self._dpi * self.scaling)

    @property
    def dpi_str(self):
        if self._dpi==None:
            return 'auto(%s)' % self.dpi
        return str(self.dpi)

    @property
    def scaling(self):
        if self._scaling==None:
            return 1.0
        return self._scaling

    @property
    def scaling_str(self):
        if self._scaling==None:
            return 'auto(%s)' % self.scaling
        return str(self._scaling)

    def set(self, width, height, scaling=None, dpi=None):
        self._width = int(width)
        self._height = int(height)
        if scaling:
            self._scaling = float(scaling)
            if self._scaling<0.1 or self._scaling>10.0:
                raise ValueError('scaling %s out of range (0.1-10.0)', self._scaling)
        else:
            self._scaling = None
        if dpi:
            self._dpi = float(dpi)

    def _asdict(self):
        return dict(self)

    def __iter__(self):
        setattr(self, '_next', 0)
        return self

    def __next__(self):
        pos = getattr(self, '_next')
        setattr(self, '_next', pos + 1)
        if pos==0:
            return ('width', self._width)
        elif pos==1:
            return ('height', self._height)
        elif pos==2 and self._scaling:
            return ('scaling', self._scaling)
        elif pos in(2, 3) and self._dpi:
            return ('dpi', self._dpi)
        delattr(self, '_next')
        raise StopIteration

    def __str__(self):
        info = '%ux%u' % (self._width, self._height)
        if self._scaling or self._dpi:
            info += 'x%s' % str(self.scaling)
            if self._dpi:
                info += 'x%u' % self.dpi
        return info

    # def __getitem__(self, key):
    #     if key==0:
    #         return self._width
    #     elif key==1:
    #         return self._height
    #     elif key==2:
    #         return self._scaling
    #     raise KeyError('invalid key. use properties width, height, scaling or dpi')

class Gui(tk.Tk):

    def __init__(self, parent):
        global AppConfig
        self._parent = parent
        AppConfig = self._parent._app_config
        self._geometry_info = Geometry()

        tk.Tk.__init__(self)
        tk.Tk.wm_title(self, AppConfig.gui.title)
        tk.Tk.report_callback_exception = self.report_callback_exception

    @property
    def fullscreen_state(self):
        return self._parent.fullscreen_state

    @fullscreen_state.setter
    def fullscreen_state(self, state):
        self._parent.fullscreen_state = state

    def report_callback_exception(self, exc, val, tb):
        # traceback.format_exception(exc, val, tb)
        self._parent.error(__name__, '%s: %s' % (exc.__class__.__name__, val))
        if AppConfig._debug:
            AppConfig._debug_exception(val)

    def mainloop(self):
        tk.Tk.mainloop(self)

    def destroy(self):
        self._parent.terminate_app()

    def quit(self):
        tk.Tk.destroy(self)
        tk.Tk.quit(self)

    def geometry(self, *args):
        self._geometry_info.set(*args)
        tk.Tk.geometry(self, '%ux%u' % (self._geometry_info.width, self._geometry_info.height))
        self.tk.call('tk', 'scaling', self._geometry_info.scaling)
        self._parent.info(__name__, 'geometry %s', self._geometry_info)

    def execute_key_binding(self, func, event=None):
        if func==Enums.KEY_BINDINGS.TOGGLE_FULLSCREEN:
            self.toggle_fullscreen()
        elif func==Enums.KEY_BINDINGS.END_FULLSCREEN:
            self.end_fullscreen()
        elif func==Enums.KEY_BINDINGS.PLOT_VISIBILITY:
            self._parent.toggle_plot_visibility()
        elif func==Enums.KEY_BINDINGS.PLOT_DISPLAY_ENERGY:
            self._parent.toggle_display_energy()
        elif func==Enums.KEY_BINDINGS.PLOT_PRIMARY_DISPLAY:
            self._parent.toggle_primary_display()
        elif func==Enums.KEY_BINDINGS.TOGGLE_DEBUG:
            self._parent.toggle_debug()
        elif func==Enums.KEY_BINDINGS.RELOAD_GUI_CONFIG:
            self._parent.reload_gui()
        elif func==Enums.KEY_BINDINGS.RELOAD_CONFIG:
            self._parent.reload_config()
        elif func==Enums.KEY_BINDINGS.RESET_PLOT:
            self._parent.reset_values()
        elif func==Enums.KEY_BINDINGS.MENU:
            pass
        elif func==Enums.KEY_BINDINGS.QUIT:
            self.destroy()
        elif func==Enums.KEY_BINDINGS.RAW_SENSOR_VALUES:
            self._parent.set_raw_values(not self._parent._raw_values)
        else:
            raise RuntimeError('invalid key binding: %s' % func)

    def handle_bind_event(self, binding, event=None):
        print('handle_bind_event', binding, event)
        self.execute_key_binding(binding)

    def init_bindings(self):
        if AppConfig.gui.fullscreen:
            if not 'win' in sys.platform:
                # self.attributes('-zoomed', True)
                self.toggle_fullscreen()
        for binding in (dir(AppConfig.gui.key_bindings)):
            if AppConfig.gui.key_bindings._is_key_valid(binding):
                value = getattr(AppConfig.gui.key_bindings, binding)
                keys = value.split(',')
                func = EnumConverter.EnumFromStr(Enums.KEY_BINDINGS, binding)
                for key in keys:
                    try:
                        self.bind(key, Tools.LambdaCaller(self.handle_bind_event, (func,)))
                    except Exception as e:
                        raise ValueError('invalid key binding: %s: %s: %s' % (key, str(func), e))

    def toggle_fullscreen(self, event=None):
        if not 'win' in sys.platform:
            self.fullscreen_state = not self.fullscreen_state
            self.attributes("-fullscreen", self.fullscreen_state)
            if self.fullscreen_state:
                self.config(cursor='none')
            else:
                self.config(cursor='')
            self._parent.set_screen_update_rate(self.fullscreen_state)
            # self._parent.window_resize()
        return "break"

    def end_fullscreen(self, event=None):
        self.fullscreen_state = False
        if not 'win' in sys.platform:
            self.attributes("-fullscreen", False)
            self.config(cursor='')
            self._parent.set_screen_update_rate(False)
        # self._parent.window_resize()
        return "break"

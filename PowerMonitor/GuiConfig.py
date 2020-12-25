#
# Author: sascha_lammers@gmx.de
#

from .Enums import PLOT_VISIBILITY, PLOT_PRIMARY_DISPLAY, DISPLAY_ENERGY
import sys

class GuiConfig(object):

    KEYS = ('plot_visibility', 'plot_primary_display', 'plot_display_energy', 'plot_time_scale', 'plot_channels')

    DEFAULTS = {
        'plot_visibility': PLOT_VISIBILITY.BOTH,
        'plot_primary_display': PLOT_PRIMARY_DISPLAY.CURRENT,
        'plot_display_energy': DISPLAY_ENERGY.WH,
        'plot_time_scale': 1.0,
        'plot_channels': [True, True, True]
    }

    def __init__(self, parent=None, data={}):
        self._parent = parent
        self._invoke_write_on_change = False
        for key, val in data.items():
            object.__setattr__(self, key, val)
        for key in self.keys():
            if not hasattr(self, key):
                object.__setattr__(self, key, data[key])

    @property
    def disabled(self):
        return not self._invoke_write_on_change

    @disabled.setter
    def disabled(self, value):
        self._invoke_write_on_change = not value

    # def __setattr__(self, key, val):
    #     if self._disabled==False and not key.startswith('_'):
    #         self._parent.write_gui_config()
    #         if self._allowed==None:
    #             return
    #         if not key in self._allowed:
    #             if self._exception:
    #                 KeyError('GuiConfig: cannot set attribute %s' % (key))
    #             return
    #     object.__setattr__(self, key, val)

    def _asdict(self):
        return dcit(self)

    def keys(self):
        return GuiConfig.KEYS

    def __iter__(self):
        setattr(self, '_next', iter(self.keys()))
        return self

    def __next__(self):
        return next(self._next)

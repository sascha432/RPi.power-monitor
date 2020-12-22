#
# Author: sascha_lammers@gmx.de
#

from enum import Enum

class PLOT_PRIMARY_DISPLAY(Enum):
    CURRENT = 0
    POWER = 1
    AGGREGATED_POWER = 2

class PLOT_VISIBILITY(Enum):
    BOTH = 0
    PRIMARY = 1
    VOLTAGE = 2

class DISPLAY_ENERGY(Enum):
    AH = 0
    WH = 1

class SCHEDULER_PRIO(Enum):
    WRITE_GUI_CONFIG = 0
    DEBUG_PING = 1
    ANIMATION = 2

class KEY_BINDINGS(Enum):
    TOGGLE_FULLSCREEN = 0
    END_FULLSCREEN = 1
    PLOT_VISIBILITY = 2
    PLOT_DISPLAY_ENERGY= 3
    PLOT_PRIMARY_DISPLAY = 4
    TOGGLE_DEBUG = 5
    RELOAD_GUI_CONFIG = 6
    RELOAD_CONFIG = 7
    RESET_PLOT = 8
    QUIT = 9
    MENU = 10

class COLOR_SCHEME(Enum):
    DARK = 0
    LIGHT = 1
    DEFAULT = 0

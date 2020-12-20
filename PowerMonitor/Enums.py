
import enum

class ANIMATION:
    RUNNING = True
    INIT = 1                      # waiting for the first callback
    READY = 0xffffa               # ready, animation is stopped
    PAUSED = 0xffffb              # animation stopped has been paused
    STATES = (INIT, READY, PAUSED)

class PLOT_PRIMARY_DISPLAY(enum.Enum):
    CURRENT = 0
    POWER = 1
    AGGREGATED_POWER = 2

class PLOT_VISIBILITY(enum.Enum):
    BOTH = 0
    PRIMARY = 1
    VOLTAGE = 2

class DISPLAY_ENERGY(enum.Enum):
    AH = 0
    WH = 1

class SCHEDULER_PRIO(enum.Enum):
    WRITE_GUI_CONFIG = 0
    DEBUG_PING = 1

class KEY_BINDINGS(enum.Enum):
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

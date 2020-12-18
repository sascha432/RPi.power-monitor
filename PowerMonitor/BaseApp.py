

class ANIMATION:
    RUNNING = True
    INIT = 1                      # waiting for the first callback
    READY = 0xffffa               # ready, animation is stopped
    PAUSED = 0xffffb              # animation stopped has been paused
    STATES = (INIT, READY, PAUSED)

class MAIN_PLOT:
    CURRENT = 0
    POWER = 1
    AGGREGATED_POWER = 2

class DISPLAY_ENERGY:
    AH = 'Ah'
    WH = 'Wh'


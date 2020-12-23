#
# Author: sascha_lammers@gmx.de
#

from matplotlib.animation import FuncAnimation
import threading
import enum
from . import SCHEDULER_PRIO

class Mode(enum.Enum):
    NONE = 0                        # not initialized
    RUNNING = 1                     # normal mode
    IDLE = 2                        # idle mode when screen is turned off
    SCHEDULED = 3                   # start scheduled

class Animation(object):

    Mode = Mode

    def __init__(self, parent, config):
        global AppConfig
        AppConfig = config

        self._parent = parent
        parent.assign_attrs(self)

        self._ani = None
        self._interval = AppConfig.plot.refresh_interval
        self._lock = threading.Lock()
        self._mode = Mode.NONE

    @property
    def lock(self):
        return self._lock

    @property
    def interval(self):
        return self._interval

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, val):
        if self._mode==val:
            return
        if self.get_interval(val)==self._interval:
            return
        self._mode = val
        self._interval = interval
        if self._ani:
            self.reset()
        else:
            self.start()

    @property
    def active(self):
        return self._mode in(Mode.RUNNING, Mode.IDLE)

    @property
    def running(self):
        return self._mode==Mode.RUNNING

    @property
    def locked(self):
        return self._lock.locked()

    # def get_interval(mode):
    #     if val==Mode.IDLE:
    #         interval = AppConfig.plot.idle_refresh_interval
    #     elif val==Mode.RUNNING:
    #         interval = AppConfig.plot.refresh_interval
    #     else:
    #         raise ValueError('invalid type: %s', type(val))

    def acquire(self, timeout=-1, blocking=True):
        self.debug('acquire timeout=%s blocking=%s', timeout, blocking)
        result = self._lock.acquire(blocking, timeout)
        if not result:
            self.error('acquiring lock failed')
        self.debug('locked')
        return result

    def release(self):
        self.debug('release')
        self._lock.release()

    def _setup(self):
        self.debug('start time=%ums', self._interval)
        if not self.acquire(5.0):
            return
        try:
            self._ani = FuncAnimation(self._parent.fig, self._parent.plot_values, interval=self._interval, blit=True)
            self._mode = Mode.RUNNING
            self._parent.canvas.draw_idle()
        except Exception as e:
            AppConfig._debug_exception(e)
        finally:
            self.release()

    def start(self):
        self.debug('start')
        self._ani.event_source.start()

    def stop(self):
        self.debug('stop')
        self._ani.event_source.stop()

    def reset(self):
        self.debug('reset %s' % self._ani)
        if not self._ani:
            return
        self.update()

    def schedule(self, time=0.5):
        if self._mode!=Mode.NONE:
            raise ValueError('animation already scheduled or running: %s', self._mode)
        self._mode = Mode.SCHEDULED
        self._parent._scheduler.enter(time, SCHEDULER_PRIO.ANIMATION, self._setup)

    def update(self):
        self.debug('update')
        if self.acquire(5.0):
            try:
                self._parent._canvas_update_required = True
                if not self._ani:
                    raise ValueError('_ani is invalid: %s' % type(self._ani))
                # self._ani._stop()
                self.stop()
                # self._ani.event_source.interval = self._interval
                # self.ani = None
                # self.ani_schedule_start()
                # self._ani.event_source.start()
                self._ani = FuncAnimation(self._parent.fig, self._parent.plot_values, interval=self._interval, blit=True)
                self.start()
                self._parent.canvas.draw_idle()
            finally:
                self.release()


Animation.Mode = Mode

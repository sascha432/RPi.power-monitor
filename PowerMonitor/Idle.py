#
# Author: sascha_lammers@gmx.de
#

from . import BaseApp
import sys

class Idle(BaseApp.BaseApp):

    def __init__(self):
        global AppConfig
        AppConfig = self._app_config
        self._state = None

    def start(self):
        self.debug(__name__, 'start')
        if AppConfig.idle_check_cmd!='':
            return
        self._state = self.get_state()
        self.thread_daemonize(__name__, self.check_idle_thread)

    def get_state(self):
        if AppConfig.check_idle_cmd=='':
            return None
        return True

    def check_idle_thread(self):
        self.thread_register(__name__)

        sleep = AppConfig.check_idle_interval
        while not self.terminate.is_set():
            if self.fullscreen_state and self.animation_is_running():
                state = self.get_state()
                if state!=self._state:
                    self._state = state
                    self.set_screen_update_rate(state)
            self.terminate.wait(sleep)

        self.thread_unregister(__name__)

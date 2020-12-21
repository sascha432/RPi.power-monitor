#
# Author: sascha_lammers@gmx.de
#

from . import BaseApp
import sys
import subprocess

class Idle(BaseApp.BaseApp):

    def __init__(self):
        global AppConfig
        AppConfig = self._app_config
        self._state = None
        self._cmd = AppConfig.idle_check_cmd.replace('{DISPLAY}', AppConfig.gui.display).split(' ')

    def start(self):
        self.debug(__name__, 'start')
        if not self._gui or AppConfig.idle_check_cmd=='':
            return
        self._state = self.get_state()
        self.thread_daemonize(__name__, self.check_idle_thread)

    def get_state(self):
        if AppConfig.idle_check_cmd=='':
            return None
        res = subprocess.call(self._cmd, shell=True)
        # self.debug(__name__, 'check idle command=%d', res)
        return res==0

    def check_idle_thread(self):
        self.thread_register(__name__)

        sleep = AppConfig.idle_check_interval
        while not self.terminate.is_set():
            if self.ani:
                state = self.get_state()
                if state!=self._state:
                    self._state = state
                    self.debug(__name__, 'check idle update rate: %s', state)
                    self.set_screen_update_rate(state)
            self.terminate.wait(sleep)

        self.thread_unregister(__name__)

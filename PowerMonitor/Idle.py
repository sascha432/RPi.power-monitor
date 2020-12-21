#
# Author: sascha_lammers@gmx.de
#

from . import BaseApp
import sys
import subprocess
import shlex
import re

class Idle(BaseApp.BaseApp):

    def __init__(self):
        global AppConfig
        AppConfig = self._app_config
        self._state = None
        self._cmd = None

    @property
    def has_idle_support(self):
        return self._gui and AppConfig.idle_check_cmd.strip()!=''

    @property
    def monitor_on():
        if self._cmd==None:
            return None
        return self._state

    @property
    def monitor_off():
        if self._cmd==None:
            return None
        return not self._state

    def reload(self):
        self._cmd = shlex.split(AppConfig.idle_check_cmd.format(DISPLAY=shlex.quote(AppConfig.gui.display)))

    def start(self):
        self.debug(__name__, 'start')
        if not self.has_idle_support:
            self._state = None
            self._cmd = None
            return
        self.reload()
        self.thread_daemonize(__name__, self.check_idle_thread)

    def _get_state(self):
        if self._cmd==None:
            return None
        state = None
        msg = ''
        try:
            p = subprocess.run(self._cmd, timeout=30, capture_output=True)
            out = p.stdout.decode()
            if p.returncode==0:
                if re.search(AppConfig.idle_check_monitor_on, out, re.I|re.M):
                    state = True
                elif re.search(AppConfig.idle_check_monitor_off, out, re.I|re.M):
                    state = False
                else:
                    self.error(__name__, 'idle command response invalid: returncode: %u: could not fiend monitor on/off pattern' % (p.returncode))
        except Exception as e:
            self.error(__name__, 'failed to execute command: %d: %s: %s' % (p.returncode, shlexy.join(self._cmd), e))

        # self.debug(__name__, 'monitor enabled: %s', state)
        return state

    def check_idle_thread(self):
        self.thread_register(__name__)

        self.terminate.wait(5)
        self._state = self.ani_get_speed_type()

        while not self.terminate.is_set():
            sleep = AppConfig.idle_check_interval
            if self.ani:
                state = self._get_state()
                if state==None:
                    sleep = 120
                elif state!=self._state:
                    self._state = state
                    self.debug(__name__, 'set interval for monitor enabled: %s', state)
                    self.set_screen_update_rate(state)
                if self._state==True:
                    sleep *= 5
            self.terminate.wait(sleep)

        self.thread_unregister(__name__)

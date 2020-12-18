#
# Author: sascha_lammers@gmx.de
#

from . import Mqtt
from . import ChannelCalibration
from .BaseApp import ANIMATION
import SDL_Pi_INA3221
from SDL_Pi_INA3221.Calibration import Calibration
from threading import Lock
import time

class Sensor(Mqtt.Mqtt):

    def __init__(self, config):
        global AppConfig
        AppConfig = config

        Mqtt.Mqtt.__init__(self, config)

        self.ina3221 = SDL_Pi_INA3221.INA3221(addr=0x40, avg=SDL_Pi_INA3221.INA3211_CONFIG.AVG_x128, shunt=1)
        self.lock = Lock()

    def init_vars(self):
        self.ina3221._calibration = ChannelCalibration(AppConfig)

    def read_sensor(self):
        try:
            while not self.terminate.is_set():
                t = time.monotonic()
                self.data['time'].append(t)
                for channel in AppConfig.channels:

                    ch = int(channel)
                    busvoltage = self.ina3221.getBusVoltage_V(ch)
                    shuntvoltage = self.ina3221.getShuntVoltage_mV(ch)
                    current = self.ina3221.getCurrent_mA(ch)
                    loadvoltage = busvoltage - (shuntvoltage / 1000.0)
                    # loadvoltage = busvoltage
                    current = current / 1000.0
                    power = (current * busvoltage)

                    self.add_stats('sensor', 1)

                    self.lock.acquire()
                    try:
                        ch = int(channel)
                        self.averages[ch]['n'] += 1
                        self.averages[ch]['U'] += loadvoltage
                        self.averages[ch]['I'] += current
                        self.averages[ch]['P'] += power

                        self.add_stats_minmax('ch%u_U' % ch, loadvoltage)
                        self.add_stats_minmax('ch%u_I' % ch, current)
                        self.add_stats_minmax('ch%u_P' % ch, power)

                        if self.energy[ch]['t']==0:
                            self.energy[ch]['t'] = t
                        else:
                            diff = t - self.energy[ch]['t']
                            # do not add if there is a gap
                            if diff<1.0:
                                self.energy[ch]['ei'] += (diff * current / 3600)
                                self.energy[ch]['ep'] += (diff * power / 3600)
                            else:
                                self.logger.error('energy error diff: channel %u: %f' % (ch, diff))
                            self.energy[ch]['t'] = t

                        self.data[ch].append((current, loadvoltage, power))

                        # self.data[ch].append({'t': t, 'I': current, 'U': loadvoltage, 'P': power })

                        if t>self.energy['stored'] + AppConfig.store_energy_interval:
                            self.energy['stored'] = t;
                            self.store_energy()
                    finally:
                        self.lock.release()


                # start when ready
                if self.animation_get_state()==ANIMATION.READY:
                    self.animation_set_state(pause=False)

                self.terminate.wait(0.1)
        except Exception as e:
            AppConfig._debug_exception(e)



#
# Author: sascha_lammers@gmx.de
#

from . import Mqtt
from . import ChannelCalibration
from . import Animation
import SDL_Pi_INA3221
import EventManager
import time
import numpy as np
import shutil
import copy
import json

INA3211_CONFIG = SDL_Pi_INA3221.INA3211_CONFIG

class Sensor(Mqtt.Mqtt):

    def __init__(self):
        # AppConfig = config
        # Mqtt.Mqtt.__init__(self, logger, config)
        global AppConfig
        AppConfig = self._app_config

        self._energy_backp_file_num = 0
        self._read_sensor_thread_state = {'quit': False}
        self._read_count = 0
        self._errors = 0

        if not self._init_ina3221_sensor():
            self._errors += 1

    def _init_ina3221_sensor(self, init_calib=False):
        if AppConfig.ina3221.auto_mode_sensor_values_per_second!=None and AppConfig.ina3221.auto_mode_sensor_values_per_second!=0:
            avg, vbus, vshunt, interval, olist = SDL_Pi_INA3221.INA3221.get_interval_params(1 / AppConfig.ina3221.auto_mode_sensor_values_per_second)
        else:
            avg = AppConfig.ina3221.averaging_mode
            vbus = AppConfig.ina3221.vbus_conversion_time
            vshunt = AppConfig.ina3221.vshunt_conversion_time
        try:
            self.ina3221 = SDL_Pi_INA3221.INA3221(addr=AppConfig.ina3221.i2c_address, avg=avg, vbus_ct=vbus, vshunt_ct=vbus, shunt=1)
            if init_calib:
                self.ina3221._calibration = ChannelCalibration(AppConfig)
        except Exception as e:
            self.error(__name__, 'exception while initializing INA3221 sensor: %s' % e)
            return False
        return True

    def start(self):
        self.debug(__name__, 'start')
        self._read_sensor_thread_listener = EventManager.Listener('read_sensor', self._event)
        self.thread_daemonize(__name__, self.read_sensor_thread)

    def init_vars(self):
        self.debug(__name__, 'init_vars')
        self._time_scale_num = 0
        self.ina3221._calibration = ChannelCalibration(AppConfig)
        self.reset_data()

    # def change_averaging_mode(self, time):
    #
    #     avg = AppConfig.ina3221.averaging_mode
    #     if time<10:
    #         avg = INA3211_CONFIG.AVERAGING_MODE.x1
    #     elif time<30:
    #         avg = INA3211_CONFIG.AVERAGING_MODE.x4
    #
    #     self.ina3221.settings(INA3211_CONFIG.ENABLE_ALL_CHANNELS, avg, AppConfig.ina3221.vbus_conversion_time, AppConfig.ina3221.vshunt_conversion_time)

    def reset_data(self):
        self.data = [[], [ [[], [], []], [[], [], []], [[], [], []] ]]
        # self.data = [[], [[[]]*3]*3]

    def read_sensor_thread_handler(self, notification):
        self.debug(__name__, 'cmd=%s data=%s', notification.data.cmd, notification.data)
        if notification.data.cmd=='quit':
            self._read_sensor_thread_state['quit'] = True
            raise EventManager.StopSleep

    def read_sensor_thread(self):
        self.thread_register(__name__)
        self.info(__name__, 'sensor read interval %.2fms' % (self.ina3221._channel_read_time * 1000))
        try:
            while not self._read_sensor_thread_state['quit']:
                if self._errors==0:
                    t = time.monotonic()
                    self.data[0].append(t)
                    for channel in AppConfig.channels:
                        ch = int(channel)
                        if channel in self.channels:
                            busvoltage, shuntvoltage, current, loadvoltage, power = (0, 0, 0, 0, 0)
                        else:
                            try:
                                busvoltage = self.ina3221.getBusVoltage_V(ch)
                                shuntvoltage = self.ina3221.getShuntVoltage_V(ch)
                                current = self.ina3221.getCurrent_mA(ch)
                                loadvoltage = busvoltage - shuntvoltage
                                current = current / 1000.0
                                power = (current * busvoltage)
                            except Exception as e:
                                self.error(__name__, 'exception while reading INA3221 sensor: %s', str(e))
                                self._errors += 1
                                busvoltage, shuntvoltage, current, loadvoltage, power = (float("nan"), float("nan"), float("nan"), 0, 0)

                        self.add_stats('sensor', 1)

                        self._data_lock.acquire()
                        try:
                            self.averages[0][ch] += 1
                            self.averages[1][ch] += loadvoltage
                            self.averages[2][ch] += current
                            self.averages[3][ch] += power

                            self.add_stats_minmax('ch%u_U' % ch, loadvoltage)
                            self.add_stats_minmax('ch%u_I' % ch, current)
                            self.add_stats_minmax('ch%u_P' % ch, power)

                            if True:
                                if self.energy[ch]['t']==0:
                                    self.energy[ch]['t'] = t
                                else:
                                    diff = t - self.energy[ch]['t']
                                    # do not add if there is a gap
                                    if diff<1.0:
                                        self.energy[ch]['ei'] += (diff * current / 3600)
                                        self.energy[ch]['ep'] += (diff * power / 3600)
                                    else:
                                        if diff>10.0:
                                            self.error(__name__, 'delay reading sensor data: channel %u: %.2fsec', ch, diff)
                                    self.energy[ch]['t'] = t

                                # self.data[ch].append((current, loadvoltage, power))
                                self.data[1][ch][0].append(loadvoltage)
                                self.data[1][ch][1].append(current)
                                self.data[1][ch][2].append(power)

                                # self.data[ch].append({'t': t, 'I': current, 'U': loadvoltage, 'P': power })

                                if t>self.energy['stored'] + AppConfig.store_energy_interval:
                                    self.energy['stored'] = t;
                                    self.store_energy()

                        finally:
                            self._data_lock.release()

                    # self.debug(__name__, 'sensor items %u', len(self.data[0]))

                        diff = time.monotonic() - t
                        diff = diff>0 and (self.ina3221._channel_read_time - diff) or 0
                        self._read_count += 1
                        self._read_sensor_thread_listener.sleep(diff, self.read_sensor_thread_handler)

                    if self._gui and self._animation.mode==Animation.Mode.NONE:
                        self.debug(__name__, 'starting animation from sensor')
                        self._animation.schedule()

                # if any error occurs, let it finish reading all channels and try to reinitilize here
                if self._errors>0:
                    self.energy[ch]['t'] = 0
                    while True:
                        self.info(__name__, 'waiting 30 seconds before trying to reintialize the sensor: errors=%u', self._errors)
                        self._read_sensor_thread_listener.sleep(30.0, self.read_sensor_thread_handler)
                        if self._read_sensor_thread_state['quit']:
                            break
                        if self._init_ina3221_sensor(True):
                            self.info(__name__, 'resetting sensor error count')
                            self._errors = 0
                            break
                        self._errors += 1

        except Exception as e:
            self.error(_name_, str(e))
            AppConfig._debug_exception(e)

        self.thread_register(__name__)


    def load_energy(self):
        files = [AppConfig.get_filename(AppConfig.energy_storage_file)]
        for i in range(0, 3):
            files.append('%s.%u.bak' % (files[0], i))
        try:
            e = None
            for file in files:
                try:
                    with open(AppConfig.get_filename(AppConfig.energy_storage_file), 'r') as f:
                        tmp = json.loads(f.read())
                        self.reset_energy()
                        for channel in self.channels:
                            ch = int(channel)
                            try:
                                t = tmp[str(ch)]
                            except:
                                t = tmp[ch]
                            self.energy[ch]['t'] = 0
                            self.energy[ch]['ei'] = float(t['ei'])
                            self.energy[ch]['ep'] = float(t['ep'])
                            e = None
                except Exception as e:
                    pass
            if e!=None:
                raise e
        except Exception as e:
            self.error(__name__, 'failed to load energy: %s: %s', e, files)
            self.reset_energy()

    def store_energy(self):
        file = AppConfig.get_filename(AppConfig.energy_storage_file)
        tmp = copy.deepcopy(self.energy)
        for channel in self.channels:
            ch = int(channel)
            del tmp[ch]['t']
        try:
            with open(file, 'w') as f:
                f.write(json.dumps(tmp))
            shutil.copyfile(file, '%s.%u.bak' % (file, self._energy_backp_file_num))
            self._energy_backp_file_num += 1
            self._energy_backp_file_num %= 3
        except Exception as e:
            self.error(__name__, 'failed to store energy: %s: %s', file, e)

    def reset_avg(self):
        self.averages = np.zeros((4, 3))

    def aggregate_sensor_values(self):
        try:
            tmp = []
            self._data_lock.acquire()
            try:
                tmp = self.data
                self.reset_data()
            finally:
                self._data_lock.release()

            n = len(tmp[0])
            if n==0:
                return

            self.compressed_min_records += n
            self.values.time().extend(tmp[0])
            for channel in self.channels:
                ch = int(channel)
                tmp2 = tmp[1][ch]
                self.values[channel].voltage().extend(tmp2[0])
                self.values[channel].current().extend(tmp2[1])
                self.values[channel].power().extend(tmp2[2])

            self.compress_values()
        except Exception as e:
            AppConfig._debug_exception(e)

    def min_max_downsample(self, x, y, num_bins, do_x=True):
        pts_per_bin = y.size // num_bins

        if do_x:
            x_view = x.reshape(num_bins, pts_per_bin)
        y_view = y.reshape(num_bins, pts_per_bin)
        i_min = np.argmin(y_view, axis=1)
        i_max = np.argmax(y_view, axis=1)

        r_index = np.repeat(np.arange(num_bins), 2)
        c_index = np.sort(np.stack((i_min, i_max), axis=1)).ravel()

        if do_x:
            return x_view[r_index, c_index]
        return y_view[r_index, c_index]

    def compress_values(self):

        try:
            t = time.monotonic()

            # remove old data
            diff_t = self.values.timeframe()
            if diff_t>AppConfig.plot.max_time:
                idx = self.values.find_time_index(AppConfig.plot.max_time)
                # self.debug(__name__, 'discard 0:%u' % (idx + 1))
                # discard from all lists
                for type, ch, items in self.values.all():
                    self.values.set_items(type, ch, items[idx + 1:])

            # compress data if min records have been added
            if self.compressed_min_records<AppConfig.plot.compression.min_records:
                return

            start_idx = self.values.find_time_index(self.compressed_ts, True)
            if start_idx==None:
                return
            end_idx = self.values.find_time_index(AppConfig.plot.compression.uncompressed_time)
            if end_idx==None:
                return
            values_per_second = AppConfig.plot.max_values / float(AppConfig.plot.max_time)
            count = end_idx - start_idx
            timeframe = self.values.timeframe(start_idx, end_idx)
            groups = timeframe * values_per_second
            if groups==0:
                return
            # split data into groups of group_size
            group_size = int(count / groups)
            if group_size>=4 and count>group_size*2:
                # find even count
                while count % group_size != 0:
                    count -= 1
                    end_idx -= 1
                n = count / group_size

                self.debug(__name__, 'compress group_size=%u data=%u:%u cnt=%u vps=%.2f total=%u' % (group_size, start_idx, end_idx, count, values_per_second, len(self.values._t)))

                old_timestamp = self.compressed_ts
                # store timestamp
                self.compressed_ts = self.values.time()[end_idx]
                self.compressed_min_records = 0

                before = len(self.values._t)

                # split array into 3 array and one of them into groups and generate mean values for each group concatenation the flattened result
                for type, ch, items in self.values.all():

                    self.add_stats('ud', len(items))

                    items = np.array_split(items[:], [start_idx, end_idx])
                    items[1] = np.array(items[1])
                    # from scipy import signal
                    # n = group_size // 2 ** 2
                    # signal.resample(items[1].tolist, 6000)
                    items[1] = self.min_max_downsample(items[1], items[1], group_size, type=='t')
                    items[1] = np.array(items[1]).reshape(-1, group_size).mean(axis=0)
                    tmp = np.concatenate(np.array(items, dtype=object).flatten()).tolist()
                    self.values.set_items(type, ch, tmp)

                    self.add_stats('cd', len(tmp))

                diff = time.monotonic() - t

                self.add_stats('cr', before - len(self.values._t))
                self.add_stats('ct', diff)

        except Exception as e:
            AppConfig._debug_exception(e)

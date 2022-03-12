#
# Author: sascha_lammers@gmx.de
#

from . import Mqtt
from . import ChannelCalibration
from . import Animation
from . import Enums
import SDL_Pi_INA3221
import EventManager
import time
import numpy as np
import shutil
import copy
import json
import copy
import random
import sqlite3

INA3211_CONFIG = SDL_Pi_INA3221.INA3211_CONFIG

class Sensor(Mqtt.Mqtt):

    ENERGY_MIN_READTIME = 0.005

    def __init__(self):
        # AppConfig = config
        # Mqtt.Mqtt.__init__(self, logger, config)
        global AppConfig
        AppConfig = self._app_config

        self._energy_backup_file_num = 0
        self._read_sensor_thread_state = {'quit': False}
        self._read_count = 0
        self._errors = 0
        self._compress_data_timeout = 0

        if not self._init_ina3221_sensor():
            self._errors += 1

    def _init_ina3221_sensor(self, init_calibration=False):
        if AppConfig.ina3221.auto_mode_sensor_values_per_second!=None and AppConfig.ina3221.auto_mode_sensor_values_per_second!=0:
            avg, vbus, vshunt, interval, o_list = SDL_Pi_INA3221.INA3221.get_interval_params(1 / AppConfig.ina3221.auto_mode_sensor_values_per_second)
        else:
            avg = AppConfig.ina3221.averaging_mode
            vbus = AppConfig.ina3221.vbus_conversion_time
            vshunt = AppConfig.ina3221.vshunt_conversion_time
        try:
            self.ina3221 = SDL_Pi_INA3221.INA3221(addr=AppConfig.ina3221.i2c_address, avg=avg, vbus_ct=vbus, vshunt_ct=vbus, shunt=1)
            if init_calibration:
                self.ina3221._calibration = ChannelCalibration(AppConfig)
        except Exception as e:
            self.error(__name__, 'exception while initializing INA3221 sensor: %s' % e)
            return False

        if self.ina3221._channel_read_time<Sensor.ENERGY_MIN_READTIME:
            print(AppConfig.ignore_warnings)
            if AppConfig.ignore_warnings<=0:
                raise RuntimeWarning("Sensor read time below minimum. %.6f<%s. Energy readings won't be available. Start with --ignore-warnings=<number>" % (self.ina3221._channel_read_time, Sensor.ENERGY_MIN_READTIME))
            AppConfig.ignore_warnings -= 1

        return True

    def start(self):
        self.debug(__name__, 'start')
        self._read_sensor_thread_listener = EventManager.Listener('read_sensor', self._event)
        self.thread_daemonize(__name__, self.read_sensor_thread)

    def init_database(self):
        try:
            cur = self._conn.cursor()
            cur.execute('CREATE TABLE IF NOT EXISTS energy ( \
                channel_id TINYINT, \
                energy_Ah REAL, \
                energy_Wh REAL, \
                updated_ts INTEGER, \
                PRIMARY KEY (updated_ts, channel_id) \
            )')
        except Exception as e:
            raise RuntimeError("Failed to create table: %s" % e)

    def init_vars(self):
        self.debug(__name__, 'init_vars')
        self._time_scale_num = 0
        self.ina3221._calibration = ChannelCalibration(AppConfig)
        self.reset_data()

    def reset_energy(self):
        self.energy = dict(enumerate([{'t': 0, 'ei': 0, 'ep': 0}]*3))
        self.energy['stored'] = 0

    def reset_data(self):
        # do not store data for GUI in headless mode
        if AppConfig.headless:
            self.data = None
        else:
            self.data = [[], [ [[], [], []], [[], [], []], [[], [], []] ]]

    def read_sensor_thread_handler(self, notification):
        self.debug(__name__, 'cmd=%s data=%s', notification.data.cmd, notification.data)
        if notification.data.cmd=='quit':
            self._read_sensor_thread_state['quit'] = True
            raise EventManager.StopSleep

    def read_sensor_thread(self):
        self.thread_register(__name__)
        self.info(__name__, 'sensor read interval %.2fms' % (self.ina3221._channel_read_time * 1000))

        try:
            file = AppConfig.get_filename(AppConfig.database_file)
            self._conn = sqlite3.connect(file)
        except Exception as e:
            msg = 'Cannot open database: %s: %s' % (file, e)
            self.error(__name__, msg)
            raise RuntimeError(msg)
        self.init_database()
        self.db_load_energy()

        try:
            while not self._read_sensor_thread_state['quit']:

                t = time.monotonic()
                if self._errors==0:
                    # read data from sensor
                    tmp = []
                    for channel in AppConfig.channels:
                        ch = int(channel)
                        if channel in self.channels: # channel enabled?
                            tmp.append((0, 0, 0, 0))
                        else:
                            try:
                                busvoltage = self.ina3221.getBusVoltage_V(ch)
                                shuntvoltage = self.ina3221.getShuntVoltage_V(ch)
                                current = self.ina3221.getCurrent_mA(ch)
                                loadvoltage = busvoltage - shuntvoltage
                                current = current / 1000.0
                                power = (current * busvoltage)
                                self.add_stats('sensor', 1)
                                tmp.append((loadvoltage, current, power, time.monotonic()))
                            except Exception as e:
                                self.add_stats('senerr', 1)
                                self.error(__name__, 'exception while reading INA3221 sensor: %s', str(e))
                                self._errors += 1
                                tmp = None
                                break

                    if self._errors==0 and len(tmp):
                        # lock'n'copy

                        # store_energy_data = None
                        diff_limit = self.ina3221._channel_read_time * len(self.channels) * 3
                        self._data_lock.acquire()
                        try:
                            if self.data:
                                self.data[0].append(t)

                            for index, (loadvoltage, current, power, ts) in enumerate(tmp):

                                self.averages[0][index] += 1
                                self.averages[1][index] += loadvoltage
                                self.averages[2][index] += current
                                self.averages[3][index] += power

                                # due to the resolution of the timestamp, energy can only be calculated precisely having an interval > 50ms
                                # precision will benefit from even longer intervals
                                if self.ina3221._channel_read_time>=Sensor.ENERGY_MIN_READTIME:
                                    if self.energy[index]['t']==0 or ts==0:
                                        self.energy[index]['t'] = ts
                                    else:
                                        diff = ts - self.energy[index]['t']
                                        # do not add if there is a gap that is over 3x times the expected read time
                                        if diff < diff_limit:
                                            self.energy[index]['ei'] += (diff * current / 3600)
                                            self.energy[index]['ep'] += (diff * power / 3600)
                                        else:
                                            if diff>diff_limit * 10:
                                                self.error(__name__, 'sensor read timeout for channel number %u: %.3fs channels: %u read time: %.6fms', (index + 1), diff, len(self.channels), self.ina3221._channel_read_time / 1000000)
                                        self.energy[index]['t'] = ts

                                    if t>self.energy['stored'] + min(30, AppConfig.store_energy_interval): # limited to >=30 seconds
                                        self.energy['stored'] = t;
                                        self.db_store_energy()


                                if self.data:
                                    self.data[1][index][0].append(loadvoltage)
                                    self.data[1][index][1].append(current)
                                    self.data[1][index][2].append(power)

                        finally:
                            self._data_lock.release()

                        if self.influx_client:
                            self.influxdb_push_data(tmp)

                        if self._gui and self._animation.mode==Animation.Mode.NONE:
                            self.debug(__name__, 'starting animation from sensor')
                            self._animation.schedule()

                        # self.debug(__name__, 'sensor items %u', len(self.data[0]))

                diff = time.monotonic() - t
                diff = diff>=0 and (self.ina3221._channel_read_time - diff) or 0
                self._read_count += 1
                self._read_sensor_thread_listener.sleep(diff, self.read_sensor_thread_handler)

                # if any error occurs, let it finish reading all channels and try to reinitialize here
                if self._errors>0:
                    self.energy[index]['t'] = 0
                    while True:
                        self.info(__name__, 'waiting 5 seconds before trying to reinitialize the sensor: errors=%u', self._errors)
                        self._read_sensor_thread_listener.sleep(5.0, self.read_sensor_thread_handler)
                        if self._read_sensor_thread_state['quit']:
                            break
                        if self._init_ina3221_sensor(True):
                            self.info(__name__, 'resetting sensor error count')
                            self._errors = 0
                            break
                        self._errors += 1

        except Exception as e:
            self.error(__name__, str(e))
            AppConfig._debug_exception(e)

        self.db_store_energy()
        if self._conn:
            self._conn.close()
            self._conn = None

        self.thread_register(__name__)


    def db_load_energy(self):
        try:
            self.reset_energy()
            statement = 'SELECT channel_id, MAX(energy_Ah) AS ei, MAX(energy_Wh) as ep FROM energy GROUP BY channel_id ORDER BY updated_ts DESC,channel_id ASC LIMIT 3'
            cur = self._conn.cursor()
            tmp = { row[0]: { 'ei': row[1], 'ep': row[2], 't': 0 } for row in cur.execute(statement) }
            self.debug(__name__, 'loaded energy from database: %s' % tmp)
            self.energy.update(tmp)

        except Exception as e:
            self.error(__name__, 'failed to load energy: %s', e)
            self.reset_energy()


    def db_store_energy(self, lock=True):
        values = []
        timestamp = time.time()
        for channel, data in self.energy.items():
            if isinstance(data, dict):
                values.append('(%u, %.16f, %.16f, %u)' % (channel, data['ei'], data['ep'], timestamp))
        statement = 'INSERT INTO energy VALUES %s' % (','.join(values))
        self.debug(__name__, statement)
        try:
            cur = self._conn.cursor()
            cur.execute(statement)
            self._conn.commit()

            statement = 'DELETE FROM energy WHERE updated_ts<%d' % (timestamp - 3600)
            cur.execute(statement)
            self._conn.commit()
            cur.execute('VACUUM')
            self._conn.commit()

        except Exception as e:
            self.error(__name__, 'failed to store energy in database: %s: %s', statement, e)

    def reset_avg(self):
        self.averages = np.zeros((4, 3))

    def _get_array_len(self):
        min_l = len(self.values._t)
        max_l = min_l
        for index, channel in enumerate(self.channels):
            min_l = min(min_l, len(self.values[index].U), len(self.values[index].I), len(self.values[index].P))
            max_l = max(max_l, len(self.values[index].U), len(self.values[index].I), len(self.values[index].P))
        return (min_l, max_l)

    def _validate_array_len(self, test_id):
        min_l, max_l = self._get_array_len()
        if min_l==max_l:
            return
        self.error(__name__, 'array length mismatch: id=%s min=%u max=%u', test_id, min_l, max_l)

    def aggregate_sensor_values(self):
        try:
            t = time.monotonic()
            tmp = []
            self._data_lock.acquire()
            try:
                tmp = copy.deepcopy(self.data)
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
                self.values[channel].U.extend(tmp2[0])
                self.values[channel].I.extend(tmp2[1])
                self.values[channel].P.extend(tmp2[2])

            if t>=self._compress_data_timeout:
                self._compress_data_timeout = t + 5
                self._scheduler.enter(1.0, Enums.SCHEDULER_PRIO.COMPRESS_DATA, self.compress_values)

            min_l, max_l = self._get_array_len()
            if min_l!=max_l:
                if min_l==0:
                    return

                tmp = {'t': len(self.values._t)}
                self.values._t = self.values._t[0:min_l]
                for index, channel in enumerate(self.channels):
                    tmp[index] = {
                        'U': len(self.values[index].U),
                        'I': len(self.values[index].I),
                        'P': len(self.values[index].P),
                    }
                    self.values[index].U = self.values[index].U[0:min_l]
                    self.values[index].I = self.values[index].I[0:min_l]
                    self.values[index].P = self.values[index].P[0:min_l]

            return True
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
                self._plot_lock.acquire()
                self._data_lock.acquire()
                try:

                    for type, ch, items in self.values.all():
                        self.values.set_items(type, ch, items[idx + 1:])
                finally:
                    self._data_lock.release()
                    self._plot_lock.release()


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

                self._plot_lock.acquire()
                self._data_lock.acquire()
                try:

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
                        # tmp = np.array(items).ravel().tolist()
                        tmp = np.concatenate(np.array(items, dtype=object).flatten()).tolist()
                        self.values.set_items(type, ch, tmp)

                        self.add_stats('cd', len(tmp))

                finally:
                    self._data_lock.release()
                    self._plot_lock.release()

                diff = time.monotonic() - t

                self.add_stats('cr', before - len(self.values._t))
                self.add_stats('ct', diff)

        except Exception as e:
            AppConfig._debug_exception(e)

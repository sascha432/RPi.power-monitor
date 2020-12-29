#
# Author: sascha_lammers@gmx.de
#

from . import Tools
from . import Idle
import hashlib
import json
import copy
import numpy as np
import EventManager
import sys
import time
try:
    from influxdb import InfluxDBClient
    influxdb = True
except:
    influxdb = False

class Influxdb(Idle.Idle):

    def __init__(self):
        global AppConfig
        AppConfig = self._app_config

        self.influx_client = None

    def start(self):
        self.debug(__name__, 'start')
        if influxdb:
            if AppConfig.influxdb.host:
                self.influx_client = InfluxDBClient(AppConfig.influxdb.host, AppConfig.influxdb.port, AppConfig.influxdb.username, AppConfig.influxdb.password, AppConfig.influxdb.database)

    def destroy(self):
        self.debug(__name__, 'destroy')
        # self._mqtt_thread_state['quit'] = True

    def init_vars(self):
        self.debug(__name__, 'init_vars')

    def influxdb_push_data(self, data):
        time_str = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.localtime())
        for index, (loadvoltage, current, power, ts) in enumerate(data):
            influx_data = {
                'measurement': 'ina3221_channel_%u' % index,
                'tags': {
                    'host': AppConfig.influxdb.tags_host
                },
                'time': time_str,
                'fields': {
                    'timestamp': ts,
                    'voltage': loadvoltage,
                    'current': current,
                    'power': power
                }
            }
            self.debug(__name__, json.dumps(influx_data))
            self.influx_client.write_points(json.dumps(influx_data))

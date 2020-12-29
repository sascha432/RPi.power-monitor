#
# Author: sascha_lammers@gmx.de
#

from . import Tools
from . import Influxdb
import hashlib
import json
import copy
import numpy as np
import EventManager
import sys

class Mqtt(Influxdb.Influxdb):

    def __init__(self):
        global AppConfig
        AppConfig = self._app_config

        self.client = None
        self.mqtt_connected = False
        self._mqtt_thread_state = {'quit': False}

    def start(self):
        self.debug(__name__, 'start')
        if AppConfig.mqtt.host:
            if self.init_mqtt():
                self.thread_daemonize(__name__, self.mqtt_thread)

    def destroy(self):
        self.debug(__name__, 'destroy')
        self._mqtt_thread_state['quit'] = True

    def init_vars(self):
        self.debug(__name__, 'init_vars')

    @property
    def mqtt_server(self):
        if self.client==None:
            return 'MQTT disabled'
        info = 'Anonymous'
        return '%s@%s:%u' % (info, AppConfig.mqtt.host, AppConfig.mqtt.port)

    @property
    def mqtt_connection(self):
        if self.client==None:
            return 'MQTT disabled'
        if self.mqtt_connected:
            info = 'Connected - '
        else:
            info = 'Disconnected - '
        return '%s' % (info, self.mqtt_server)

    def init_mqtt(self):
        try:
            import paho.mqtt.client
        except:
            paho = False

        if paho==False:
            self.client = None
            self.error(__name__, 'paho mqtt client not avaiable. MQTT support disabled')
            return False

        self._mqtt_thread_listener = EventManager.Listener('mqtt', self._event)

        self.client = paho.mqtt.client.Client(clean_session=True)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        if False:
            self.client.on_log = self.on_log
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.will_set(AppConfig.mqtt.get_status_topic(), payload=AppConfig.mqtt.payload_offline, qos=1, retain=True)

        return True

    def end_mqtt(self):
        if self.mqtt_connected:
            self.info(__name__, 'disconnecting from MQTT server')
            self.client.disconnect(True)
            self.client.loop_stop()
            self.mqtt_connected = False

    def mqtt_publish_auto_discovery(self):
        mac_addresses = Tools.get_mac_addresses()

        for entity, unit in AppConfig.mqtt.AGGREGATED:
            payload = self.create_hass_auto_conf(entity, 0, unit, entity, mac_addresses)
            topic = AppConfig.mqtt.get_auto_discovery_topic(0, entity)
            self.debug(__name__, 'auto discovery %s: %s' % (topic, payload))
            self.client.publish(topic, payload=payload, qos=1, retain=True)

        for channel in self.channels:
            for entity, unit in AppConfig.mqtt.ENTITIES.items():
                payload = self.create_hass_auto_conf(entity, channel.number, unit, entity, mac_addresses)
                topic = AppConfig.mqtt.get_auto_discovery_topic(channel.number, entity)
                self.debug(__name__, 'auto discovery %s: %s', topic, payload)
                self.client.publish(topic, payload=payload, qos=1, retain=True)

    def on_log(self, client, userdata, level, buf):
        self.debug(__name__, '%s: %s', level, buf)

    def on_connect(self, client, userdata, flags, rc):
        self.debug(__name__, 'on_connect rc=%u', rc)
        self.mqtt_connected = False
        if rc==0:
            self.add_stats('mqtt_con', 1)
            try:
                self.mqtt_connected = True
                self.client.publish(AppConfig.mqtt.get_status_topic(), AppConfig.mqtt.payload_online, qos=1, retain=True)
                if AppConfig.mqtt.auto_discovery:
                    self.mqtt_publish_auto_discovery()
            except Exception as e:
                self.error(__name__, 'Failed to connect to MQTT server %s. Reconnecting in 30 seconds: %s', self.mqtt_server, e)
                AppConfig._debug_exception(e)

                self.terminate.wait(30)
                if not self.terminate.is_set():
                    self.client.reconnect()

    def on_disconnect(self, client, userdata, rc):
        self.debug(__name__, 'on_disconnect rc=%u', rc)
        self.mqtt_connected = False

    def create_hass_auto_conf(self, entity, channel, unit, value_json_name, mac_addresses):

        m = hashlib.md5()
        m.update((':'.join([AppConfig.mqtt.device_name, AppConfig.mqtt.MODEL, AppConfig.mqtt.MANUFACTURER, str(channel), entity, value_json_name])).encode())
        unique_id = m.digest().hex()[0:11]

        m = hashlib.md5()
        m.update((':'.join([AppConfig.mqtt.device_name, AppConfig.mqtt.MODEL, AppConfig.mqtt.MANUFACTURER, entity, value_json_name])).encode())
        device_unique_id = m.digest().hex()[0:11]

        connections = []
        for mac_addr in mac_addresses:
            connections.append(["mac", mac_addr])

        return json.dumps({
            'name': '%s-%s-ch%u-%s' % (AppConfig.mqtt.device_name, AppConfig.mqtt.sensor_name, channel, entity),
            'platform': 'mqtt',
            'unique_id': unique_id,
            'device': {
                'name': '%s-%s-%s' % (AppConfig.mqtt.device_name, AppConfig.mqtt.sensor_name, device_unique_id[0:4]),
                'identifiers': [ device_unique_id, '947bc81af46aa573a62ccefadb9c9a7aef6d1c1e' ],
                'connections': connections,
                'model': AppConfig.mqtt.MODEL,
                'sw_version': AppConfig.VERSION,
                'manufacturer': AppConfig.mqtt.MANUFACTURER
            },
            'availability_topic': AppConfig.mqtt.get_status_topic(),
            'payload_available': AppConfig.mqtt.payload_online,
            'payload_not_available': AppConfig.mqtt.payload_offline,
            'state_topic': AppConfig.mqtt.get_channel_topic(channel),
            'unit_of_measurement': unit,
            'value_template': '{{ value_json.%s }}' % value_json_name
        }, ensure_ascii=False, indent=None, separators=(',', ':'))

    def mqtt_thread_handler(self, notification):
        self.debug(__name__, 'cmd=%s data=%s', notification.data.cmd, notification.data)
        if notification.data.cmd=='quit':
            self._mqtt_thread_state['quit'] = True
            raise EventManager.StopSleep
        elif notification.data.cmd=='reconnect':
            selt.client.reconnect()
            raise EventManager.StopSleep

    def mqtt_thread(self):
        self.thread_register(__name__)

        self.client.connect(AppConfig.mqtt.host, port=AppConfig.mqtt.port, keepalive=AppConfig.mqtt.keepalive)
        self.client.loop_start()

        raw_values = None

        while not self._mqtt_thread_state['quit']:
            sleep_time = 5
            if not self.mqtt_connected or np.sum(self.averages[0])<3:
                # wait for connection and enough data
                pass
            elif self._raw_values:
                # disable MQTT when raw values are displayed
                raw_values = True
            elif raw_values and not self._raw_values:
                # wait 60 seconds after raw values have been disabled
                sleep_time = 60
                raw_values = False
            elif raw_values==False:
                # 60 seconnds are over, reset average and continue broadcasting
                raw_values = None
                self._data_lock.acquire()
                try:
                    self.reset_avg()
                finally:
                    self._data_lock.release()
            else:

                sleep_time = AppConfig.mqtt.update_interval
                tmp = None
                self._data_lock.acquire()
                try:
                    averages = [np.divide(self.averages[1], self.averages[0]), np.divide(self.averages[2], self.averages[0]), np.divide(self.averages[3], self.averages[0])]
                    self.reset_avg()
                    tmp2 = copy.deepcopy(self.energy)
                finally:
                    self._data_lock.release()

                kwh_precision = [(.001, 6), (.01, 5), (.1, 4), (1.0, 3), (100.0, 2), (None, 0)]

                try:
                    sum_P = 0
                    sum_E = 0

                    for n in range(0, 3):
                        payload = json.dumps({
                            'U': self.format_float_precision(averages[0][n]),
                            'I': self.format_float_precision(averages[1][n]),
                            'P': self.format_float_precision(averages[2][n]),
                            'EI': self.format_float_precision(tmp2[n]['ei']),
                            'EP': self.format_float_precision(tmp2[n]['ep'] / 1000, kwh_precision), # ep is Wh, we send kWh
                        })

                        sum_P += averages[2][n]
                        sum_E += tmp2[n]['ep']

                        topic = AppConfig.mqtt.get_channel_topic(n + 1)
                        self.info(__name__, 'publish %s: %s', topic, payload)
                        self.client.publish(topic, payload=payload, qos=AppConfig.mqtt.qos, retain=False)

                        n += 1

                    payload = json.dumps({
                        'P': self.format_float_precision(sum_P),
                        'E': self.format_float_precision(sum_E / 1000, kwh_precision),  # E is Wh, we send kWh
                    })
                    topic = AppConfig.mqtt.get_channel_topic(0)
                    self.debug(__name__, 'publish %s: %s', topic, payload)
                    self.client.publish(topic, payload=payload, qos=AppConfig.mqtt.qos, retain=False)

                    self.add_stats('mqtt_pub', 1)

                except Exception as e:
                    self.error(__name__, 'error: %s: reconnecting...', e)
                    AppConfig._debug_exception(e)
                    self.client.reconnect()

            self._mqtt_thread_listener.sleep(sleep_time, self.mqtt_thread_handler)

        self.end_mqtt()

        self.thread_unregister(__name__)
#
# Author: sascha_lammers@gmx.de
#

try:
    import paho.mqtt.client
except:
     paho = False

class Mqtt(object):

    def __init__(self, config):
        global AppConfig
        AppConfig = config

    def init_mqtt(self):
        if paho==False:
            self.logger.error('paho mqtt client not avaiable. MQTT support disabled')
            return False
        self.client = paho.mqtt.client.Client(clean_session=True)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        if False:
            self.client.on_log = self.on_log
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

        self.client.will_set(AppConfig.mqtt.get_status_topic(), payload=AppConfig.mqtt.payload_offline, qos=AppConfig.mqtt.qos, retain=True)
        self.logger.debug("MQTT connect: %s:%u" % (AppConfig.mqtt.host, AppConfig.mqtt.port))
        self.client.connect(AppConfig.mqtt.host, port=AppConfig.mqtt.port, keepalive=AppConfig.mqtt.keepalive)
        self.client.loop_start();
        return True

    def end_mqtt(self):
        if self.mqtt_connected:
            self.client.disconnect(True)
            self.mqtt_connected = False

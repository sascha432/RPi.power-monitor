#!/usr/bin/python3
#
# Author: sascha_lammers@gmx.de
#

import logging
import sys
import MainApp
from MainApp import AppConfig
from MainApp import MqttConfig
from MainApp import MainApp
from MainApp import ConfigLoader
import signal
import os
import socket
import argparse

parser = argparse.ArgumentParser(description='Power Monitor')
parser.add_argument('-C', '--config-dir', help='location of config.json and energy.json', type=str, default=os.path.realpath(os.path.join(os.environ.get('HOME'), '.power_monitor')))
parser.add_argument('--display', help='override DISPLAY variable', type=str, default=None)
parser.add_argument('--headless', help='start without GUI', action='store_true', default=None)
parser.add_argument('--fullscreen', help='start in fullscreen mode', action='store_true', default=None)
parser.add_argument('--verbose', help='enable debug output', action='store_true', default=None)
parser.add_argument('--check', help='check and display configuration', action='store_true', default=False)
parser.add_argument('--debug', help='enable debug mode', action='store_true', default=False)

args = parser.parse_args()

if args.debug:
    args.verbose = True
    AppConfig._debug = True

AppConfig.init(args.config_dir)
MqttConfig.init(socket.gethostname())
ConfigLoader.load_config(args, True)

default_handler = logging.StreamHandler(stream=sys.stdout)
default_handler.setLevel(AppConfig.verbose and logging.DEBUG or logging.INFO)
logger = logging.getLogger('power_monitor')
logger.setLevel(logging.DEBUG)
logger.addHandler(default_handler)

if AppConfig.headless!=True:
    if AppConfig.display=='$DISPLAY':
        AppConfig.display = os.environ.get('DISPLAY')
        if not AppConfig.display:
            logger.warning('DISPLAY not set, forcing headless mode')
            AppConfig.headless = True
    else:
        os.environ['DISPLAY'] = AppConfig.display

if args.check:
    print("---")

    def config_key(key, dct):
        if not AppConfig.is_valid_key(key):
            return False
        return isinstance(dct[key], (str, int, float, bool))

    for channel in AppConfig.channels:
        d = channel.__dict__
        for key in filter(lambda key: config_key(key, d), d.keys()):
            print('channel[%u].%s=%s%s' % (d['n'], key, d[key], channel.get_default(key)))
    d = AppConfig.__dict__
    for key in filter(lambda key: config_key(key, d), d.keys()):
        print('app.%s=%s%s' % (key, d[key], AppConfig.get_default(key)))
    d = MqttConfig.__dict__
    for key in filter(lambda key: config_key(key, d), d.keys()):
        print('mqtt.%s=%s%s' % (key, d[key], MqttConfig.get_default(key)))
    sys.exit(0)

app = MainApp(logger)

def signal_handler(signal, frame):
    logger.debug('exiting, signal %u...' % signal)
    app.destroy()
    app.quit()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

app.start()
app.mainloop()

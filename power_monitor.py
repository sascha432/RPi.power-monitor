#!/usr/bin/python3
#
# Author: sascha_lammers@gmx.de
#

import logging
import sys
import os
import socket
import argparse
from collections import ChainMap
from PowerMonitor import MainApp
from PowerMonitor import AppConfig
from PowerMonitor.Config import Config

parser = argparse.ArgumentParser(description='Power Monitor')
parser.add_argument('-C', '--config-dir', help='location of config.json and energy.json', type=str, default=os.path.realpath(os.path.join(os.environ.get('HOME'), '.power_monitor')))
parser.add_argument('--display', help='override DISPLAY variable', type=str, default=None)
parser.add_argument('--headless', help='start without GUI', action='store_true', default=None)
parser.add_argument('--fullscreen', help='start in fullscreen mode', action='store_true', default=None)
parser.add_argument('--daemon', help='run as daemon', action='store_true', default=None)
parser.add_argument('--verbose', help='enable debug output', action='store_true', default=None)
parser.add_argument('--check', help='check configuration', action='store_true', default=None)
parser.add_argument('--debug', help='enable debug mode', action='store_true', default=None)

args = parser.parse_args()

if args.debug:
    args.verbose = True

AppConfig.Mqtt.device_name = socket.gethostname()

try:
    config = Config(args.config_dir)
    config.load(config.get_filename('config.json'), AppConfig.app)
except Exception as e:
    parser.error('failed to load configuration: %s' % e)

if args.verbose!=None:
    AppConfig.app.verbose = args.verbose
if args.headless!=None:
    AppConfig.app.headless = args.headless
if args.daemon!=None:
    AppConfig.app.daemon = args.daemon
if args.display!=None:
    AppConfig.app.gui.display = args.display
if args.fullscreen!=None:
    AppConfig.app.gui.fullscreen = args.fullscreen

default_handler = logging.StreamHandler(stream=sys.stdout)
default_handler.setLevel(AppConfig.app.verbose and logging.DEBUG or logging.INFO)
logger = logging.getLogger('power_monitor')
logger.setLevel(logging.DEBUG)
logger.addHandler(default_handler)

if AppConfig.app.headless!=True:
    if AppConfig.app.gui.display=='$DISPLAY':
        AppConfig.app.gui.display = os.environ.get('DISPLAY')
        if not AppConfig.app.gui.display:
            logger.warning('DISPLAY not set, forcing headless mode')
            AppConfig.app.headless = True
    else:
        os.environ['DISPLAY'] = AppConfig.app.gui.display

if args.check:
    print('OK')
    sys.exit(0)

app = MainApp(logger)
app.init_signal_handler()

if AppConfig.daemon:
    thread = threading.Thread(target=lambda: app.mainloop(), args=(), daemon=True)
    thread.start()
    logger.debug('started...')
else:
    app.mainloop()

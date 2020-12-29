#!/usr/bin/python3
#
# Author: sascha_lammers@gmx.de
#

import logging
import sys
import os
import socket
import argparse
import threading
from pathlib import Path
from Config import (JsonWriter, YamlWriter)
from PowerMonitor.MainApp import MainApp
from PowerMonitor import AppConfig
from PowerMonitor.Config import Config

if 'win' in sys.platform:
    home_dir = os.environ.get('APPDATA')
else:
    home_dir = Path.home()
config_dir = os.path.realpath(os.path.join(home_dir, '.power_monitor'))

parser = argparse.ArgumentParser(description='Power Monitor')
parser.add_argument('-C', '--config-dir', help='location of config.json and energy.json', type=str, default=config_dir)
parser.add_argument('--display', help='override DISPLAY variable', type=str, default=None)
parser.add_argument('--headless', help='start without GUI', action='store_true', default=None)
parser.add_argument('--fullscreen', help='start in fullscreen mode', action='store_true', default=None)
parser.add_argument('--daemon', help='run as daemon', action='store_true', default=None)
parser.add_argument('--verbose', help='enable debug output', action='store_true', default=None)
parser.add_argument('--check', help='check configuration', action='store_true', default=None)
parser.add_argument('--print', help='check and display configuration', choices=['json', 'yaml', 'raw'], default=None)
parser.add_argument('--section', help='config section to display', type=str, default=None)
parser.add_argument('--key', help='config key(s) to display', action="append", nargs='*', default=None)
parser.add_argument('--debug', help='enable debug mode', action='store_true', default=None)
parser.add_argument('--ignore-warnings', help='number of warnings to ignore and continue', type=int, default=0)

args = parser.parse_args()

if args.debug:
    args.verbose = True
if args.print:
    args.check = True

AppConfig.Mqtt.device_name = socket.gethostname()
AppConfig.config_dir = args.config_dir

try:
    config = Config(args.config_dir)
    root_object = config.load(config.get_filename('config.json'))
except Exception as e:
    if args.debug:
        raise e
    parser.error('failed to load configuration: %s' % e)

setattr(sys.modules[AppConfig.App.__module__], AppConfig.App.__class__.__qualname__, root_object)
AppConfig = root_object
AppConfig.channels = dict(zip(range(0, 3), list(AppConfig.channels)))
setattr(AppConfig, 'get_filename', config.get_filename)

AppConfig.ignore_warnings = args.ignore_warnings
if args.verbose!=None:
    AppConfig.verbose = args.verbose
if args.headless!=None:
    AppConfig.headless = args.headless
if args.daemon!=None:
    AppConfig.daemon = args.daemon
if args.display!=None:
    AppConfig.gui.display = args.display
if args.fullscreen!=None:
    AppConfig.gui.fullscreen = args.fullscreen
AppConfig._debug = args.debug

default_handler = logging.StreamHandler(stream=sys.stdout)
default_handler.setLevel(AppConfig.verbose and logging.DEBUG or logging.INFO)
logger = logging.getLogger('power_monitor')
logger.setLevel(logging.DEBUG)
try:
    import colorlog
    default_handler.setFormatter(colorlog.ColoredFormatter('%(log_color)s%(levelname)s:%(message)s'))
    # default_handler.setFormatter(colorlog.ColoredFormatter('%(log_color)s%(levelname)s:%(name)s:%(message)s'))
    default_handler.setFormatter(formatter)
except:
    pass
logger.addHandler(default_handler)

if AppConfig.headless!=True:
    if AppConfig.gui.display=='$DISPLAY':
        AppConfig.gui.display = os.environ.get('DISPLAY')
        if not AppConfig.gui.display:
            logger.error('DISPLAY not set, forcing headless mode')
            AppConfig.headless = True
    else:
        os.environ['DISPLAY'] = AppConfig.gui.display

if args.check:
    if args.print==None:
        print('OK')
    else:
        config.print_config(args.print, (args.section, args.key and args.key[0] or None))
    sys.exit(0)


app = MainApp(logger, AppConfig)

if AppConfig.daemon:
    app.daemonize(True)
else:
    app.daemonize(False)


#!/usr/bin/python3
#
# Author: sascha_lammers@gmx.de
#

import logging
import sys
import MainApp
import signal
import os

default_handler = logging.StreamHandler(stream=sys.stdout)
default_handler.setLevel(logging.DEBUG)
logger = logging.getLogger('power_monitor')
logger.setLevel(logging.DEBUG)
logger.addHandler(default_handler)

display = os.environ.get('DISPLAY')
app = MainApp.MainApp(logger, init_gui=display!=None and display!='')

def signal_handler(signal, frame):
    logger.debug('exiting, signal %u...' % signal)
    app.destroy()
    app.quit()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

app.start()
app.mainloop()

#
# Author: sascha_lammers@gmx.de
#

class EVENT_MANAGER:
    class THREAD:
        ANY = ''
        MULTIPLE = None
    class PRIORITY:
        LOWEST = -10
        LOW = -5
        NORMAL = 0
        HIGH = 5
        HIGHEST = 10

class EventData(object):
    def __init__(self, data):
        self._data = data

    def __getattr__(self, key):
        return self._data[key]

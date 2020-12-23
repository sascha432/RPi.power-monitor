#
# Author: sascha_lammers@gmx.de
#

from PowerMonitor.AppConfig import Channel
import numpy as np

class PlotValues(object):
    def __init__(self, channel: Channel):
        self._channel = channel
        self.U = []
        self.P = []
        self.I = []

    def __len__(self):
        return len(self.U)

    def __setattr__(self, key, val):
        if not key.startswith('_') and not key in ('U', 'I', 'P'):
            raise KeyError('attribute %s readonly' % key)
        object.__setattr__(self, key, val)

    def items(self):
        return (
            ('U', self.U),
            ('I', self.I),
            ('P', self.P)
        )

    def clear(self):
        self.U.clear()
        self.P.clear()
        self.I.clear()

class PlotValuesContainer(object):

    def __init__(self, channels):
        self._values = []
        for channel in channels:
            self._values.append(PlotValues(channel))
        self._t = []

    def clear(self):
        self._t.clear()
        for val in self._values:
            val.clear()

    def __getitem__(self, key):
        if isinstance(key, Channel):
            return self._values[int(key)]
        return self._values[key]

    # def append_time(self, list):
    #     self._t += list

    def max_time(self):
        if self._t:
            return self._t[-1]
        return 0

    def timeframe(self, start=0, end=-1):
        if len(self._t):
            return self._t[end] - self._t[start]
        return 0.0

    def time(self):
        return self._t

    def find_time_index(self, time_val, timestamp=False, func=None):
        time_max = self.max_time()
        if func!=None:
            f = filter(lambda t: func(t), self._t)
        elif timestamp:
            f = filter(lambda t: t > time_val, self._t)
        else:
            f = filter(lambda t: time_max - t <= time_val, self._t)
        element = next(f, None)
        if element==None:
            return None
        return self._t.index(element)

    def set_items(self, type_str, channel, items):
        if type_str=='t':
            self._t = items
        elif channel<0 or channel>=len(self._values):
            raise ValueError('invalid channel: %u: type: %s' % (channel, type_str))
        elif type_str in ('U', 'I', 'P'):
            object.__setattr__(self._values[channel], type_str, items)

    def items(self):
        tmp = []
        for values in self._values:
            tmp.append((values._channel, values))
        return tmp

    def values(self):
        return self._values

    def all(self):
        tmp = [('t', 0, self._t)]
        for values in self._values:
            for type, items in values.items():
                tmp.append((type, int(values._channel), items))
        return tmp

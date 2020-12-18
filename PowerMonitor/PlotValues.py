#
# Author: sascha_lammers@gmx.de
#

from PowerMonitor.AppConfig import Channel

class PlotValues(object):
    def __init__(self, channel: Channel):
        if not isinstance(channel, Channel):
            raise TypeError('Channel')
        self._channel = channel
        self.clear()

    def __avg_attr(self, attr, num = 10):
        values = object.__getattribute__(self, attr)
        if not values:
            raise ValueError('no values in list: %s' % attr)
            # return 0
        if num>len(values):
            return np.average(values)
        return np.average(values[-num:])

    def __min_attr(self, attr):
        values = object.__getattribute__(self, attr)
        if not values:
            raise ValueError('no values in list: %s' % attr)
            # return None
        return min(values)

    def __max_attr(self, attr):
        values = object.__getattribute__(self, attr)
        if not values:
            raise ValueError('no values in list: %s' % attr)
            # return None
        return max(values)

    def avg_U(self, num=10):
        return self.__avg_attr('U', num)

    def avg_I(self, num=10):
        return self.__avg_attr('I', num)

    def avg_P(self, num=10):
        return self.__avg_attr('P', num)

    def min_U(self):
        return self.__min_attr('U')

    def min_I(self):
        return self.__min_attr('I')

    def min_P(self):
        return self.__min_attr('P')

    def max_U(self):
        return self.__max_attr('U')

    def max_I(self):
        return self.__max_attr('I')

    def max_P(self):
        return self.__max_attr('P')

    def voltage(self):
        return self.U

    def current(self):
        return self.I

    def power(self):
        return self.P

    def __len__(self):
        return len(self.U)

    def set_items(self, type_str, items):
        if type_str in self._keys:
            tmp = object.__getattribute__(self, type_str)
            tmp = items.copy()
            return
        raise AttributeError('invalid type: %s' % type_str)

    def items(self):
        return self._items

    def clear(self):
        self.U = []
        self.P = []
        self.I = []
        self._keys = ('U', 'I', 'P')
        self._items = [
            ('U', self.U),
            ('I', self.I),
            ('P', self.P)
        ]

class PlotValuesContainer(object):

    def __init__(self, channels):
        self._values = []
        for channel in channels:
            self._values.append(PlotValues(channel))
        self._t = []

    def clear(self):
        self._t = []
        for val in self._values:
            val.clear()

    def __getitem__(self, key):
        if isinstance(key, ChannelConfig):
            return self._values[int(key)]
        return self._values[key]

    def append_time(self, list):
        self._t += list

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
            tmp = object.__getattribute__(self, '_t')
            tmp = items.copy()
        elif channel<0 or channel>=len(self._values):
            raise ValueError('invalid channel: %u: type: %s' % (channel, type_str))
        else:
            self._values[channel].set_items(type_str, items)

    def items(self):
        tmp = []
        for values in self._values:
            tmp.append((values._channel, values))
        return tmp

    def all(self):
        tmp = [('t', 0, self._t)]
        for values in self._values:
            for type, items in values.items():
                tmp.append((type, int(values._channel), items))
        return tmp
# Author: sascha_lammers@gmx.de
#

from . import *
import itertools
import types
import re

class Converter(object):

    # call from subclass to validate the value
    def convert(self, value, param):
        param.validate_type(value)
        return value

    # static method to create Converter() from attr
    # argument 1: list, tuple, range, iterable, filter or generator
    def __call__(obj, *args):
        if isinstance(args[0], type):
            return obj.create_instance(args[1])
        return obj.create_instance(args[0])

    def create_instance(value):
        if value==None:
            return None
        try:
            iterator = iter(value)
            return IteratorConverter(iterator)
        except:
            pass
        if isinstance(value, range):
            return RangeConverter(value)
        if isinstance(value, types.GeneratorType):
            return GeneratorConverter(value)
        raise TypeError('object is not iterable: %s' % (Type.name(value)))

class MarginConverter(Converter):

    def top_value(value):
        return Param(value, (int, float), (MarginConverter, (True)))

    def bottom_value(value):
        return Param(value, (int, float), (MarginConverter, (False)))

    #
    # Converts percentage value in multiplier for adding a margin
    #
    # top=True
    # 5 = 1.05 or 105%
    # -5 = 0.95 or 95%
    # top=False
    # 40 = 0.4 or 40%
    # -40 = 0.6 or 60%
    #
    def __init__(self, top=True):
        self._top = top

    def convert(self, value, param):
        margin = value / 100.0
        if self._top==(margin>=0):
            margin += 1.0
        else:
            margin = 1.0 - margin
        return margin

class TimeConverter(Converter):

    def value(value, default_unit='s'):
        return Param(value, (int, float, str), (TimeConverter, (default_unit)))

    def __init__(self, default_unit='s'):
        self._unit = default_unit

    def _get_unit_to_second_multiplier(self, unit):
        if unit in('us','µs') or unit.startswith('micros'):
            return 0.000001
        if unit=='ms' or unit.startswith('millis'):
            return 0.001
        if unit=='s' or unit.startswith('sec'):
            return 1
        if unit=='m' or unit.startswith('min'):
            return 60
        if unit=='h' or unit.startswith('hour'):
            return 3600
        if unit=='d' or unit.startswith('day'):
            return 86400
        if unit=='w' or unit.startswith('week'):
            return 604800
        raise ValueError('Invalid time unit: %s: (w=weeks,d=days,h=hours,m=minutes,s=seconds,ms=milliseconds,us=microseconds)' % unit)

    def convert(self, value, param):
        if isinstance(value, (int, float)):
            return value

        Converter.convert(self, value, param)
        unit = re.sub(r'[0-9\.\s]', '', value) # remove digits, dot and spaces
        if unit=='':
            unit = self._unit

        val = float(re.sub(r'[a-zA-Z]*$|\s', '', value)) # remove a-z and any spaces
        m1 = self._get_unit_to_second_multiplier(unit)
        m2 = self._get_unit_to_second_multiplier(self._unit)
        val = val * (m1 / m2)
        if int(val)==val:
            val = int(val)
        return val

class ListConverter(Converter):

    def value(value, items):
        return Param(value, (object,), (ListConverter, (items)))

    def __init__(self, items):
        self._items = items

    def ValueError(self, value, items, limit=16):
        if len(items)>limit:
            n = max(1, (limit / 2) - 1)
            items = '%s ... %s' % (str(items[0:n])[0:-1], str(items[-n:])[1:])
        return ValueError('invalid value: %s: expected: %s' % (value, items))

    def convert(self, value, param):
        if not value in self._items:
            raise self.ValueError(self._items)
        return value

class IteratorConverter(ListConverter):

    def value(value, iterator):
        return Param(value, (object,), (IteratorConverter, (iterator)))

    def __init__(self, iterator):
        self._iterator = iterator

    def convert(self, value, param):
        self._iterator, tmp = itertools.tee(self._iterator)
        if not value in tmp:
            self._iterator, tmp = itertools.tee(self._iterator)
            raise self.ValueError(list(tmp))
        return value

class GeneratorConverter(IteratorConverter):

    def value(value, generator):
        return Param(value, (object,), (GeneratorConverter, (generator)))

    def __init__(self, generator):
        IteratorConverter.__init__(iter(generator))
        self._generator = generator

class RangeConverter(Converter):

    def value(value, range_obj, types=(object,)):
        return Param(value, types, (RangeConverter, (range_obj)))

    def __init__(self, range_obj):
        self._range = range_obj

    def convert(self, value, param):
        if not value in self._range:
            _min = self._range[0]
            step = self._range[1] - _min
            _max = self._range[-1]
            step = abs(step)!=1 and (' step %d' % -step) or ''
            raise ValueError('invalid value: %s: expected: %d to %d%s' % (value, _min, _max, step))
        return value

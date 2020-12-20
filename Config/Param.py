#
# Author: sascha_lammers@gmx.de
#

from . import *
import sys
import copy
from enum import Enum

class DEFAULT():
    def __init__(self, value):
        self._value = value

    def __eq__(self, val):
        if self._value in(True, False):
            return val
        return None

DEFAULT.ALLOW = DEFAULT(True)
DEFAULT.EXCEPTION = DEFAULT(False)

class Param(object):
    class ReadOnly:
        pass

    #
    # default       default value
    # type          type, tuple or Type object of allowed types
    # converter     callable, list, range, Converter object
    #               the function converts or validates the passed value. the type is validated before
    #               raise an exception to indicate an invalid value
    # name          name of the parameter
    #
    def __init__(self, default=None, types=(), converter=None, name=None):
        if isinstance(default, Param):
            raise RuntimeError('value must not be type Param')
        self._name = name
        if callable(default) and (types==None or len(types)==0):
            # types will be set when resolving default value
            self._types = None
        else:
            if isinstance(types, Type):
                self._types = types
            else:
                self._types = Type(types)
        self._default = default
        self._converter = converter
        self._is_default = True
        self._value = None
        self._raw_value = self._value

    @property
    def default(self):
        return self._default

    @default.setter
    def set_default(self, value):
        self._default = value

    @property
    def value(self):
        if self.is_default:
            raise ValueError('value not set: %s' % self.name)
        return self._value

    @value.setter
    def value(self, value):
        self._is_default = False
        self._raw_value = value
        self._value = self.prepare_value(value)

    def set_value(self, value):
        self.value = value

    @property
    def raw_value(self):
        if self.is_default:
            return self.default
        return self._raw_value

    @property
    def is_default(self):
        return self._is_default

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def types(self):
        return self._types

    def __str__(self):
        if self.is_default:
            value = 'value=<DEFAULT>'
        else:
            if self.value!=self.raw_value:
                value = 'value=%s raw_value=%s' % (self.value, self.raw_value)
            else:
                value = 'value=%s' % self.value

        default = self.prepare_value(self.default, True)
        if default!=self.default:
            default = 'default=%s raw_default=%s' % (default, self.default)
        else:
            default = 'default=%s' % default

        return 'name=%s %s %s types=%s' % (self.name, value, default, self.types)

    def prepare_value(self, value, any_type=False):
        if any_type==False and not type(value)==self._types:
            if not isinstance(value, int) or float!=self.types:
                raise TypeError('type %s not allowed: %s: %s' % (Type.name(value), self.types, self.name))
            # convert int to float
            value = float(value)

        if self._converter==None:
            return value

        # lazy object creation
        if isinstance(self._converter, tuple):
            if not isinstance(self._converter[1], tuple):
                raise TypeError('converter arguments not tuple: %s: %s' % (Type.name(self._converter[1]), Type.name(self._converter[0])))
            # create converter object
            self._converter = self._converter[0](*self._converter[1])

        return self._converter.convert(value, self)

    def is_type_allowed(self, value):
        if Param.ReadOnly==self.types:
            return False
        if isinstance(self._default, Enum) and self._converter==None:
            from .Converter import EnumConverter
            self._converter = EnumConverter(type(self._default))
            self._types = Type((str, int, float, type(self._default)))

        if isinstance(value, int) and float==self.types:
            return True
        return type(value)==self.types

    def validate_type(self, value):
        if Param.ReadOnly==self.types:
            return False
        if value==self.types:
            raise TypeError('allowed types: %s' % self.types)

    # def convert_value(self, value, converter):
    #     if isinstance(self._converter, Converter):
    #         return self._converter.convert(value, self)
    #     self.validate_type(value)
    #     if callable(converter):
    #         return converter(value)
    #     return value

    def finalize(self, path):
        if callable(self.default):
            self._default = self.default(path)
        if self.types==None:
            self._types = Type(type(self.default))

    #
    # create Param object
    #
    # value     tuple, Param or value
    # path      path of the parameter
    #
    #   default value     allowed types will be set to type of default value
    #   (default value, (types,))
    #   (default value, (types,), converter)
    #       converter can be a list, range, callable or Converter object to convert and/or validate the value
    #
    # if default value is callable, it will be called to get the default value
    # the argument is path
    #
    def create_instance(obj, value):
        if isinstance(value, Param):
            return copy.deepcopy(value)
        if isinstance(value, tuple) and isinstance(value[0], Param):
            return copy.deepcopy(value[0])

        if not isinstance(value, tuple):
            types = (type(value),)
            converter = None
        else:
            value += (None, None, None)
            value, types, converter, = value[0:3]

        if isinstance(converter, (tuple, list)) and len(converter)==2 and callable(converter[0]):
            if isinstance(converter[1], (tuple, list)):
                return converter[0].__call__(*converter[1])
            else:
                return converter[0].__call__(converter[1])

        if callable(converter):
            if not hasattr(sys.modules[__name__], 'Converter'):
                from . import Converter
            if isinstance(converter.__class__, Converter): # static method
                converter = Converter.create_instance(converter)

        return Param(value, types, converter)

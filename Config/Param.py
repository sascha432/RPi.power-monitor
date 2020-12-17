#
# Author: sascha_lammers@gmx.de
#

from . import Type
from . import Index
import sys
import copy

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

    def __str__(self):
        return 'name=%s default=%s value=%s types=%s' % (self.name, self._default, self.get_value('<DEFAULT>'), self._types)

    @property
    def default(self):
        return self._default

    def set_value(self, value):
        self._value = self.prepare_value(value)

    def prepare_value(self, value):
        if not type(value)==self._types:
            if isinstance(value, int) and float==self._types:
                value = float(value)
            else:
                raise TypeError('type %s not allowed: %s' % (Type.name(value), self._types))
        if self._converter!=None:
            if callable(self._converter):
                value = self._converter(value, self)
            else:
                if isinstance(self._converter, tuple):
                    self._converter = self._converter[0](self._converter[1])
                value = self._converter.convert(value, self)
        return value

    # default
    #   DEFAULT.ALLOW         return default value if value is not set
    #   DEFAULT.EXCEPTION     raise exception if value is not set
    #   any                   return default
    def get_value(self, default=DEFAULT.ALLOW):
        if not hasattr(self, '_value'):
            if isinstance(default, DEFAULT):
                if default==True:
                    return self._default
                if default==False:
                    raise ValueError('value not set: %s' % self._name)
            return default
        return self._value

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def types(self):
        return self._types

    def is_type_allowed(self, value):
        if Param.ReadOnly==self._types:
            return False
        if isinstance(value, int) and float==self._types:
            return True
        return type(value)==self._types

    def validate_type(self, value):
        if Param.ReadOnly==self._types:
            return False
        if value==self._types:
            raise TypeError('allowed types: %s' % self._types)

    def convert_value(value, converter):
        if isinstance(self._converter, Converter):
            return self._converter.convert(value, self)
        self.validate_type(value)
        if callable(converter):
            return converter(value)
        return value

    def finalize(self, path):
        if callable(self._default):
            self._default = self._default(path)
            if self._types==None:
                self._types = Type(type(self._default))

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

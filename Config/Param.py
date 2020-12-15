#
# Author: sascha_lammers@gmx.de
#

from . import *

class Param(object):

    #
    # default       default value
    # type          type, tuple or Type object of allowed types
    # converter     callable, list or range
    #               the function converts or validates the passed value. the type is validated before
    #               raise an exception to indicate an invalid value
    #
    def __init__(self, default=None, types=(), converter=None):
        self._types = isinstance(types, Type) and types or Type(types,converter=Type.jsonname)
        self._default = default
        self._converter = lambda value: value

    def get_default(self):
        return self._default

    def get_types(self):
        return self._types

    def is_type_allowed(self, type):
        return type == self._types

    def convert_value(value, converter):
        if isinstance(converter, list):
            if not value in converter:
                raise ValueError('invalid value: %s: expected: %s' % (value, converter))
        if isinstance(converter, (range)):
            if not value in converter:
                iterator = iter(converter)
                step = next(iterator) - next(iterator)
                step = abs(step)!=1 and (' step: %d' % -step) or ''
                raise ValueError('invalid value: %s: expected: %u-%u%s' % (value, min(converter), max(converter), step))
        return converter(value)

    def get_validated_value(self, value):
        if value == self._types:
            raise TypeError('allowed types: %s' % self._types)
        return self._converter(value)

    #
    # create Param() from attr
    # default value, tuple or list (default value, (types)[, converter])
    #
    # class my_config:
    #   def check(value):
    #     if len(value)<4:
    #       raise ValueError()
    #     return True
    #   host = (None, str)                                      # allow to set a string as hostname, default is None
    #   port = 80                                               # default is 80 and allowed type int will be added
    #   ip_or_host = ('192.168.0.1', (,), my_config.check)      # default is str, allowed type str will be added and func() called to convert/validate the ip/host
    #
    def from_attr(obj, attr):
        value = getattr(obj, attr)
        try:
            n = len(value)
            if n>2:
                return Param(value[0], types=value[1], converter=value[2])
            if n>1:
                return Param(value[0], types=value[1])
            return Param(value[0], types=(type(value[0]),))
        except:
            return Param(value, types=(type(value),))


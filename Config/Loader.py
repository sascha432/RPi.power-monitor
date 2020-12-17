#
# Author: sascha_lammers@gmx.de
#

from . import (Root, Base, ListBase)
from . import (DictType, RangeType)
from . import Path
from . import Type
from . import Param
import copy

class Loader(object):

    def __init__(self, name, config):
        self._debug = False
        # self._debug = print
        self._root = Root(name, config)
        self._create_root()

    def load(self, filename):
        pass

    def _create_params(self, obj):
        if self._debug:
            self._debug('_create_params item=%s keys=%s' % (Type.name(obj), [name for name in dir(obj) if obj._is_key_valid(name)]))

        # add attributes first
        for name in dir(obj):
            value = None
            param = None
            try:
                if obj._is_key_valid(name) and hasattr(obj, name):
                    value = getattr(obj, name)
                    param = Param.create_instance(obj, value)
                    if param!=None:
                        if self._debug:
                            self._debug('_set_param(attr) name=%s item=%s parent=%s path=%s default=%s types=%s ' % (name, Type.name(obj), Type.name(obj), obj._path + name, param.default, param.types))
                        obj._set_param(name, param)
            except Exception as e:
                # add more info
                raise RuntimeError('type=%s path=%s: %s' % (Type.name(obj), obj._path + name, e))

            if self._debug and param==None and obj._is_key_valid(name):
                raise RuntimeError('param==None path=%s hasattr=%s' % (obj._path + name, hasattr(obj, name)))

        # add parameters and override existing attributes
        for name, param in obj._get_struct().items():
            if isinstance(param, Param):
                if self._debug:
                    self._debug('_set_param(struct) name=%s item=%s parent=%s path=%s default=%s types=%s ' % (name, Type.name(obj), Type.name(obj), obj._path + name, param.default, param.types))
                obj._set_param(name, param)


    def _create_root(self):
        self._root._set_path(Path())
        self._create_children(self._root._child, self._root._child._get_struct(), self._root)
        self._create_params(self._root._child)

    def _add_object(self, name, obj, parent):
        obj._set_path(parent._path + name)
        if self._debug:
            self._debug("_add_object item=%s parent=%s path=%s" % (Type.name(obj), Type.name(parent), obj._path))
        parent._add_child(obj)
        self._root[obj._path] = obj

    def _create_children(self, obj, struct, parent):
        if self._debug:
            self._debug('_create_children obj=%s struct=%s path=%s parent=%s' % (Type.name(obj), Type.name(struct), parent._path, Type.name(parent)))
        if isinstance(struct, DictType):
            for name, child in struct.items():
                if isinstance(child, Base):
                    self._add_object(name, child, obj)
                    self._create_children(child, child._get_struct(), obj)
                    self._create_params(child)
        elif isinstance(struct, RangeType):
            for index in struct._range:
                range_struct = copy.deepcopy(struct._get_struct())
                child = struct._item_type(range_struct, index)
                self._add_object(index, child, obj)
                self._create_children(child, range_struct, obj)
                self._create_params(child)

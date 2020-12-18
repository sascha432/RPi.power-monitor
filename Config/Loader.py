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

    @property
    def root_name(self):
        return self._root._root_name

    @property
    def root_object(self):
        return self._root._object

    @property
    def root(self):
        return self._root

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
                raise RuntimeError('type=%s path=%s\n%s' % (Type.name(obj), obj._path + name, e))

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
        self._create_children(self._root._object, self._root._object._get_struct(), self._root)
        self._create_params(self._root._object)

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


class Merger(object):

    def __init__(self, root):
        self._root = root

    # if set_defaults is False, only the structure will be created
    def _set_default_values(self, set_defaults):
        for path, obj in self._root._objects.items():
            if not path.endswith(']'):
                path = Path(path)
                setattr(obj._parent, path.name, obj)
            if set_defaults:
                for name, param in obj._param_items():
                    setattr(obj, param.name, param.default)

    def _merge_config(self, config, path):
        for key, val in config.items():
            if isinstance(val, list):
                index = 0
                for item in val:
                    self._merge_config(item, path + key + index)
                    index += 1
            elif isinstance(val, dict):
                self._merge_config(val, path + key)
            else:
                path_str = str(path)
                if not path_str in self._root:
                    raise KeyError('parameter does not exist. path=%s name=%s' % (path_str, key))
                setattr(self._root[path_str], key, val)


    # create the config tree inside root merging default values with given configuration
    #
    # values are not validated, but the attributes must exist
    # ObjectWriter can validate any object and fill it with default values
    # if config contains all values, set_defaults can be set to False
    def merge(self, config, set_defaults=True):
        self._set_default_values(set_defaults)
        self._merge_config(config, Path())

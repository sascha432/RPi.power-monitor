#
# Author: sascha_lammers@gmx.de
#

from . import Path
from . import DictType

class Base(object):

    def __init__(self, struct, path=None):
        if isinstance(struct, dict):
            struct = DictType(struct)
        self._struct = struct
        self._path = Path(path)
        self._params = {}

    def _set_path(self, path):
        if not isinstance(path, Path):
            path = Path(path)
        self._path = path
        return self

    # returns value of parameter
    def __getitem__(self, path_name):
        return self._get_param(path_name).get_value()

    def __setitem__(self, path_name, value):
        self._get_param(path_name).set_value(value)

    def __contains__(self, path_name):
        return path_name in self._params

    def _param_keys(self):
        return self._params.keys()

    def _param_values(self):
        return self._params.values()

    def _param_items(self):
        return self._params.items()

    # get Param object
    def _get_param(self, path_name):
        if not self.__contains__(path_name):
            raise NameError('parameter %s does not exist' % path_name)
        return self._params[path_name]

    # set Param object
    def _set_param(self, path_name, param):
        param.name = path_name
        param.finalize(self._path)
        self._params[path_name] = param

    def _get_children(self):
        if hasattr(self, '_children'):
            return self._children
        return []

    def _add_child(self, obj):
        obj._parent = self
        if hasattr(self, '_children'):
            self._children.append(obj)
        else:
            self._children = [obj]

    def _get_struct(self):
        return self._struct

    # keys starting with _ and UPPERCASE_ONLY are invalid
    # override to validate keys for the section
    def _is_key_valid(self, name):
        return Path._is_key_valid(name)

class ListBase(Base):
    def __init__(self, struct, path=None):
        Base.__init__(self, struct, path)
        self._children = []

    def __setitem__(self, key, val):
        self._children[key] = val

    def __getitem__(self, key):
        return self._children[key]

    def __contains__(self, key):
        return key in self._children

    def __len__(self):
        return len(self._children)

class ItemBase(Base):
    def __init__(self, struct, index, path=None):
        Base.__init__(self, struct, path)
        self._index = index

class Root(Base):
    def __init__(self, name, child):
        child._set_path(Path(name))
        child._parent = self
        Base.__init__(self, {}, child._path)
        self._parent = None
        # self._children = [child]
        self._root_name = name
        self._objects = {name: child}
        self.__setattr__(name, child)

    @property
    def _object(self):
        return self._objects[self._root_name]

    def _get_children(self):
        return [self._objects[self._root_name]]

    def __setitem__(self, key, obj):
        self._objects[str(key)] = obj

    def __getitem__(self, key):
        return self._objects[str(key)]

    def __contains__(self, key):
        return str(key) in self._objects

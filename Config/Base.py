#
# Author: sascha_lammers@gmx.de
#

from . import *

class Base(object):

    def __init__(self, name, struct, index=None, path=None):
        self._name = name
        self._struct = struct
        self._index = index
        self._path = Path(path)

    def _setup(self, path, index=None):
        if index!=None and not isinstance(index, int):
            raise TypeError('index not int: %s' % type_name(index))
        self._index = index
        self._path = Path(path)
        return self

    def _add_param(self, name: str, param: Param):
        if hasattr(self, '_params'):
            if hasattr(self._params, name):
                raise KeyError('duplicate parameter: %s' % name)
            self._params[name] = param
        else:
            self._params = {name: param}

    def _add_object(self, obj):
        if hasattr(obj, '_objects'):
            self._objects.append(obj)
        else:
            self._objects = [self, obj]

    def _add_child(self, obj):
        if hasattr(self, '_children'):
            self._children.append(obj)
        else:
            self._children = [obj]

    def path(self):
        return self._path[self._index]

    def path_name(self):
        parts = self._path._parts
        if len(parts)==0:
            return ''
        return parts[-1]

    # keys starting with _ and UPPERCASE_ONLY are invalid
    def _is_key_valid(self, obj, key):
        if not (key.startswith('_') or key.upper()==key):
            return False
        return True

    def _resolve_key(key):
        split_key = key.split('.')
        for section in split_key:
            if not BaseConfig._is_key_valid(None, key):
                raise KeyError('invalid key: section %s: %s' % (section, '.'.join(split_key)))

        for obj in self._objects:
            print(dir(obj))
            try:
                print(obj.__name__, tmp)
                tmp = BaseConfig._resolve_key_in(obj, split_key)
                return tmp
            except:
                pass
        raise KeyError('key not found: section %s: %s' % (split_key[-1], '.'.join(split_key[0:-1])))

    def _resolve_key_in(obj, key):
        if isinstance(key, str):
            key = key.split('.')
        if key[0] == self._struct:
            key.pop(0)

        print(obj, key)

        obj = self._root
        for section in key[0:-1]:
            print(dir(obj),section)
            # if not BaseConfig._is_key_valid(obj, section):
            #     raise KeyError('invalid key: %s: %s' % (section, '.'.join(key)))
            if not hasattr(obj, section):
                raise KeyError('key not found: section %s: %s' % (section, '.'.join(key)))
            obj = getattr(obj, section)

        if not hasattr(obj, section):
            raise KeyError('key not found: section %s: %s' % (section, '.'.join(key)))
        return (obj, section)

    def _get(self, key):
        (obj, attr) = self._resolve_key(key)
        value = getattr(obj, attr)
        if isinstance(value, (list, tuple)) and len(value)>1:
            return value[0]
        return value;

    def _set(self, key, value):
        (obj, attr) = self._resolve_key(key)
        data = getattr(obj, attr)
        if not (isinstance(data, (list, tuple)) and len(data)>1):
            data = (data, (type(data),), data)
        if not isinstance(value, data[1]):
            raise TypeError('')
        data = (value, data[1], data[2])
        setattr(obj, data)


class ListBase(Base):
    def __init__(self, name, struct, index=None, path=None):
        Base.__init__(self, struct, index, path)
        self._children = []

    def __setitem__(self, key, val):
        self._items[key] = val

    def __getitem__(self, key):
        return self._items[key]

    def __contains__(self, key):
        return key in self._children

    def __len__(self):
        return len(self._children)


class Root(Base):
    def __init__(self):
        Base.__init__(self, None, None)

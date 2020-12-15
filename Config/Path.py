#
# Author: sascha_lammers@gmx.de
#

from . import *

class Path(object):

    def _is_key_valid(key):
        return not (key.startswith('_') or key.upper()==key)

    def __init__(self, path=None):
        if path==None:
            self._parts = list()
        elif isinstance(path, Path):
            self._parts = path._parts.copy()
        elif isinstance(path, str):
            self._parts = path.split('.')
        elif isinstance(path, (list)):
            self._parts = path
        else:
            raise TypeError('path not (None,list,str,Path): %s' % (type_name(path)))

    def __add__(self, name):
        if name==None:
            return self
        if not isinstance(name, str):
            raise TypeError('name not str: %s' % type_name(name))
        return Path(self._parts + [name])

    def __str__(self):
        return '.'.join(self._parts)

    def __list__(self):
        return self._parts

    def __len__(self):
        return len(self._parts)

    def __getitem__(self, key):
        if key==None:
            return str(self)
        if not isinstance(key, int):
            raise TypeError('key not int: %s' % type_name(key))
        if not len(self):
            raise ValueError('root path cannot have an index')
        return str(self) + '[%u]' % key

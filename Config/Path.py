#
# Author: sascha_lammers@gmx.de
#

from . import Type

class Index(object):
    def __init__(self, name: str, index: int):
        self._name = name
        self._index = index

    def __str__(self):
        return '%s[%u]' % (self._name, self._index)

    def __repr__(self):
        return str((self._name, self._index))

    @property
    def name(self):
        return self._name

    @property
    def index(self):
        return self._index

class Parts(list):
    def __init__(self, parts=[]):
        list.__init__(self, parts)

    def copy(self):
        return self.__copy__()

    def __copy__(self):
        return Parts(list.copy(self))

    def __str__(self):
        return '.'.join([str(p) for p in self])

    def prefix(self, prefix):
        return '.'.join([str(p) for p in [prefix] + self])

class Path(object):

    def _is_key_valid(key):
        if not (key.startswith('_') or key.upper()==key):
            return True
        return False

    # create new Path object
    #
    # args
    #   None or no arguments
    #   (Parts,Path,str,list)[,[str[,int],(str,int)]]
    #
    def __init__(self, *args):

        if len(args)==0 or args[0]==None:
            self._parts = Parts()
        elif len(args)>=1:

            if isinstance(args[0], Parts):
                self._parts = args[0].copy()
            elif isinstance(args[0], Path):
                self._parts = args[0].parts.copy()
            elif isinstance(args[0], str):
                self._parts = Parts(args[0].split('.'))
            elif isinstance(args[0], list):
                self._parts = Parts(args[0])
            else:
                raise TypeError('expected (Parts,Path,str,list) as first argument: %s' % (Type.name(args[0])))

            if len(args)==2:
                if isinstance(args[1], tuple):
                    self._parts.append(Index(args[1][0], args[1][1]))
                else:
                    self._parts.append(args[1])
            elif len(args)==3:
                self._parts.append(Index(args[1], args[2]))

    def __copy__(self):
        return Path(self)

    def copy(self):
        return self.__copy__()

    def __add__(self, value):
        if value==None:
            return Path(self)
        if isinstance(value, int):
            return Path(self._parts[0:-1], (self._parts[-1], value))
        if isinstance(value, str):
            return Path(self._parts, value)
        raise TypeError('expected int,str: %s' % Type.name(value))

    def __str__(self):
        return str(self._parts)

    def __repr__(self):
        return str(self._parts)

    def __len__(self):
        return len(self._parts)

    @property
    def parts(self):
        return list(self._parts)

    @property
    def name(self):
        if len(self._parts)==0:
            return ''
        return self._parts[-1]

    @property
    def index(self):
        if len(self._parts)==0 or not isinstance(self._parts[-1], Index):
            return None
        return self._parts[-1]._index

# if __name__ == '__main__':

#     l = []
#     l.append(Path())
#     l.append(Path(None))
#     l.append(Path('key1', 'key2', 5))
#     l.append(Path('key1', ('key2', 6)))
#     l.append(Path(['key1']))
#     l.append(Path(['key1', 'key2']))
#     l.append(Path(['key1', 'key2'], 'key3'))
#     l.append(Path(['key1', 'key2'], 'key3', 0))
#     l.append(Path(['key1', 'key2']) + 'key3')
#     l.append(Path(['key1', 'key2']) + 'key3' + 'key4')
#     l.append(Path(['key1', 'key2']) + 'key3' + 'key4' + 0)
#     l.append(Path(Parts(['key1', 'key2'])))

#     for p in l:
#         print('path=%s name=%s index=%s parts=%s' % (p, p.name, p.index, p.parts))

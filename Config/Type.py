#
# Author: sascha_lammers@gmx.de
#

def type_str(arg):
    return Type.qualname(arg)

def type_name(arg):
    return Type.name(arg)

def type_json(arg):
    return Type.jsonname(arg)

def typeof(arg, qualname=False):
    return qualname and Type.qualname(arg) or Type.name(arg)

class Type:

    NoneTypeMapping = 'none'
    BuiltinsFormat = '<%s>'
    JsonTypeMapping = [
        ('null', (type(None))),
        ('string', (str)),
        ('number', (float,int,complex)),
        ('boolean', (bool)),
        ('object', (dict)),
        ('array', (list,tuple,set,frozenset,list)),
    ]

    def _format_builtins(arg):
        return Type.BuiltinsFormat % arg

    def __init__(self, types=[], converter=type_name):
        try:
            self._types = iter(types)
        except:
            self._types = (types,)
        self._converter = converter

    def __eq__(self, arg):
        return arg in self._types

    def __str__(self):
        return self._format()

    def _format(self):
        return Type.format(self._types, converter=self._converter)

    #
    # format types
    #
    # types         single type, tuple or list
    # sep           separator
    # fmt           format string or None for returning a list of strings
    # converter     callable to convert type to string
    #
    def format(types, sep=',', fmt='%s', converter=type_name):
        try:
            parts = [converter(t) for t in types]
        except:
            parts = [converter(types)]
        if fmt==None:
            return parts
        return fmt % sep.join(parts)

    def name(arg):
        if arg==None:
            return Type.NoneTypeMapping
        if isinstance(arg, type):
            name = arg.__name__
            return Type._format_builtins(name)
        name = object.__repr__(arg)[1:].split(' ')[0]
        name = name.split('.')[-1]
        return name

    def qualname(arg):
        if arg==None:
            return Type.NoneTypeMapping
        if isinstance(arg, type):
            p = []
            m = arg.__module__
            if m not in (None, int.__module__):
                p.append(m)
            p.append(arg.__qualname__)
            name = '.'.join(p)
            return Type._format_builtins(name)
        name = object.__repr__(arg)[1:].split(' ')[0]
        return name

    def jsonname(arg):
        try:
            return next(filter(lambda row: isinstance(arg, row[1]), Type.JsonTypeMapping))[0]
        except StopIteration:
            return Type.name(arg)


# if __name__=='__main__':

#     from Type import Type
#     import pprint
#     import sys

#     class Bla:
#         class BlaSub:
#             CONSTA='a'
#         def func():
#             pass
#         def method():
#             pass

#     class str:
#         pass

#     items = [
#         pprint._safe_key,
#         list,
#         str,
#         Bla,
#         Bla.BlaSub,
#         Bla(),
#         Bla.BlaSub(),
#         Bla.BlaSub.CONSTA,
#         pprint.pprint,
#         Bla.func,
#         Bla.method,
#         Bla().func,
#         Bla().method,
#         9,
#         0.0,
#         '1',
#         'xx',
#         [1, 2, 3],
#         (1, 2),
#         {'a': 1},
#         (),
#         None,
#         False,
#         complex(1.0),
#         frozenset('frozen'.split())
#     ]

#     fmt = '%-{0}.{0}s | %-{1}.{1}s | %-{2}.{2}s | %-{3}.{3}s | %-{4}.{4}s'.format(25, 16, 16, 32, 40)

#     title = fmt % ('type_str()', 'type_name()', 'type_json', 'type()', 'repr()')
#     print(title)
#     print('-'*len(title))
#     for item in items:
#         print(fmt % (type_str(item), type_name(item), type_json(item), type(item), object.__repr__(item)))

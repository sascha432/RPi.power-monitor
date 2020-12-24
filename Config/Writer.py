#
# Author: sascha_lammers@gmx.de
#

#
# Write class that creates an object or outputs the configuration tree
#

from . import Type
from . import Index
from . import Path
import json
import sys
from pprint import pprint
from enum import Enum

class Writer(object):
    def __init__(self, root, output=sys.stdout, section=None):
        self._root = root
        self._indent = 0
        self._output = output
        self._config = None
        self._keys = None
        if isinstance(section, tuple):
            section, self._keys = section
        self._section = isinstance(section, str) and Path(section) or section

    def _indent_str(self, level):
        return ' ' * (level * self._indent)

    def _path(self, path):
        return str(path)
        # return path._parts.join(prefix=self._root._root_name)

    def _dump_child(self, obj, level):
        print("%spath=%s type=%s parent=%s struct=%s" % (self._indent_str(level), self._path(obj._path), Type.name(obj), Type.name(obj._parent), Type.name(obj._struct)), file=self._output)

    def _dump_param(self, obj, index, param, level):
        print("%s<%s> %s" % (self._indent_str(level), self._path(obj._path + param.name), param), file=self._output)

    def _dump(self, obj, level):
        if len(obj._path)==0 or obj._path.startswith(self._section):
            if len(obj._path)==0:
                self._dump_child(obj, level)
            elif obj._path==self._section:
                self._dump_child(obj, level)
                index = 0
                for param in obj._param_values():
                    if self._keys==None or param.name in self._keys:
                        self._dump_param(obj, index, param, level + 1)
                    index += 1
            for child in obj._get_children():
                self._dump(child, level + 1)

    def dumps(self, indent=2):
        self._indent = indent
        self._dump(self._root, 0)


class YamlWriter(Writer):
    def __init__(self, root, output=sys.stdout, section=None):
        Writer.__init__(self, root, output, section)

    def _escape(self, value):
        if isinstance(value, str):
            tmp = value.replace("'", "''")
            return "'%s'" % tmp
        elif isinstance(value, bool):
            return str(value).lower()
        elif value==None:
            return '~'
        return str(value)

    def _dump_child(self, obj, level):
        if level>=0:
            if obj._path.startswith(self._section):
                if obj._path.index!=None:
                    print('%s- ' % (self._indent_str(level)), end='', file=self._output)
                else:
                    print('%s%s:' % (self._indent_str(level), len(obj._path) and obj._path.name or self._root._root_name), file=self._output)

    def _dump_param(self, obj, index, param, level):
        if not obj._path==self._section:
            return
        if obj._path.index!=None and index==0:
            indent = ''
        else:
            indent = self._indent_str(level)
        print('%s%s: %s' % (indent, param.name, self._escape(param.raw_value)), file=self._output)

    def dumps(self, indent=2, skip_root_name=False):
        self._indent = indent
        self._dump(self._root._object, skip_root_name and -1 or 0)

class ObjectWriter(Writer):
    def __init__(self, root, output=sys.stdout, section=None):
        Writer.__init__(self, root, output, section)

    def _dump(self, obj):
        objs = {}
        if obj._path.startswith(self._section):
            if obj._path==self._section:
                index = 0
                for param in obj._param_values():
                    if self._keys==None or param.name in self._keys:
                        objs[param.name] = param.raw_value
                    index += 1
            for child in obj._get_children():
                tmp = self._dump(child)
                name = child._path.name
                if isinstance(name, str):
                    objs.update(tmp)
                elif isinstance(name, Index):
                    if name.index==0:
                        objs = [tmp]
                    else:
                        objs.append(tmp)
        if not obj._path.startswith(self._section):
            return {}
        if len(obj._path)>1 and not isinstance(obj._path.name, Index):
            return {obj._path.name: objs}
        return objs

    def create_object(self):
        return self._dump(self._root._object)

    def dumps(self, indent=2):
        pprint(self.create_object(), stream=self._output)

class JsonWriter(ObjectWriter):
    def __init__(self, root, output=sys.stdout, section=None):
        ObjectWriter.__init__(self, root, output, section)

    def dumps(self, indent=2):
        print(json.dumps(self.create_object(), indent=indent), file=self._output)

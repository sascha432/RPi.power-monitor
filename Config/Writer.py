#
# Author: sascha_lammers@gmx.de
#

from . import Type
from . import Index
import json
import sys

class Writer(object):
    def __init__(self, root, output=sys.stdout):
        self._root = root
        self._indent = 0
        self._output = output

    def _indent_str(self, level):
        return ' ' * (level * self._indent)

    def _path(self, path):
        return path._parts.prefix(self._root._root_name)

    def _dump_child(self, obj, level):
        print("%spath=%s type=%s parent=%s struct=%s" % (self._indent_str(level), self._path(obj._path), Type.name(obj), Type.name(obj._parent), Type.name(obj._struct)), file=self._output)

    def _dump_param(self, obj, index, param, level):
        print("%spath=%s name=%s param=%s" % (self._indent_str(level), self._path(obj._path + param.name), param.name, param), file=self._output)

    def _dump(self, obj, level):
        self._dump_child(obj, level)
        index = 0
        for param in obj._param_values():
            self._dump_param(obj, index, param, level + 1)
            index += 1
        for child in obj._get_children():
            self._dump(child, level + 1)

    def dumps(self, indent=2):
        self._indent = indent
        self._dump(self._root, 0)


class YamlWriter(Writer):
    def __init__(self, root, output=sys.stdout):
        Writer.__init__(self, root, output)

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
        if obj._path.index!=None:
            print('%s- ' % (self._indent_str(level)), end='', file=self._output)
        else:
            print('%s%s:' % (self._indent_str(level), len(obj._path) and obj._path.name or self._root._root_name), file=self._output)

    def _dump_param(self, obj, index, param, level):
        if obj._path.index!=None and index==0:
            indent = ''
        else:
            indent = self._indent_str(level)
        print('%s%s: %s' % (indent, param.name, self._escape(param.get_value())), file=self._output)


class JsonWriter(Writer):
    def __init__(self, root, output=sys.stdout):
        Writer.__init__(self, root, output)

    def _dump(self, obj):
        json = {}
        index = 0
        for param in obj._param_values():
            json[param.name] = param.get_value()
            index += 1
        for child in obj._get_children():
            tmp = self._dump(child)
            name = child._path.name
            if isinstance(name, str):
                json.update(tmp)
            elif isinstance(name, Index):
                if name.index==0:
                    json = [tmp]
                else:
                    json.append(tmp)
        if len(obj._path) and not isinstance(obj._path.name, Index):
            return {obj._path.name: json}
        return json

    def create_object(self):
        return self._dump(self._root._child)

    def dumps(self, indent=2):
        print(json.dumps(self.create_object(), indent=indent), file=self._output)

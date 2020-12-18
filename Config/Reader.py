#
# Author: sascha_lammers@gmx.de
#

from . import ObjectWriter
from . import (Path, Parts)
from . import Index
from . import Type
import json
import sys

class JsonReader(object):

    def __init__(self, root, use_config_root=True):
        self._root = root
        self._use_config_root = use_config_root
        self._json = ObjectWriter(root).create_object()

    def _loads_from(self, file):
        with open(file, 'r') as f:
            config = f.read()
            try:
                config = json.loads(config)
            except Exception as e1:
                # try with commentjson
                json.decoder.JSONDecodeError
                try:
                    import commentjson
                except Exception as e2:
                    raise RuntimeError('json.loads() failed: %s\nfailed to import commentjson: %s' % (e1, e2))
                config = commentjson.loads(config)

            if self._use_config_root==False:
                return {self._root._root_name: config}
            return config

    def _last_path(self, path):
        n = len(path)
        for i in range(1, n + 1):
            if not str(Path(path._parts[0:i])) in self._root:
                n = i
                break
        return Path(path._parts[0:n - 1])

    def _loads(self, json, path):
        for key, val in json.items():
            if isinstance(val, list):
                index = 0
                for item in val:
                    self._loads(item, path + key + index)
                    index += 1
            elif isinstance(val, dict):
                self._loads(val, path + key)
            else:
                path_str = str(path)
                if not path_str in self._root:
                    raise KeyError("%s: section '%s' does not exist: failed after: %s" % (path, path.name, self._last_path(path)))
                obj = self._root[path_str]
                if not key in obj:
                    raise KeyError("%s: parameter '%s' does not exist: path: %s" % (path, key))
                param = obj._get_param(key)
                if not param.is_type_allowed(val):
                    raise KeyError("%s: type '%s' not allowed: %s" % (path + key, Type.name(val), param.types))
                val = param.prepare_value(val)
                json[key] = val

    def loads_from(self, file):
        return self.loads(self._loads_from(file))

    def loads(self, json):
        self._loads(json, Path())
        return json



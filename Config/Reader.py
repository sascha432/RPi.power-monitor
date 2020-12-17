#
# Author: sascha_lammers@gmx.de
#

from . import JsonWriter
# writer = Config.YamlWriter(loader._root)
# # writer = Config.JsonWriter(loader._root)
# writer.dumps()

class JsonReader(object):
    def __init__(self, root):
        self._json = JsonWriter(root).create_object()

    def loads_from(self, file):
        with open(file, 'r') as f:
            self.loads(f.read())

    def loads(self, json):
        pass

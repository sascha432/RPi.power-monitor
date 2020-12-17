#
# Author: sascha_lammers@gmx.de
#

class StructType(object):
    pass

# Param and StructType
class DictType(dict, StructType):
    def __init__(self, items={}):
        dict.__init__(self, items)


# list of Param and StructType
class RangeType(StructType):
    def __init__(self, index, item_type, struct=DictType()):
        self._range = index
        self._item_type = item_type
        self._struct = struct

    def items(self):
        return []

    def _get_struct(self):
        return self._struct

class ListType(StructType):
    def __init__(self, item_type, struct=DictType()):
        self._item_type = item_type
        self._struct = struct

    def items(self):
        return []

    def _get_struct(self):
        return self._struct

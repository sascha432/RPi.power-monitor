#
# Author: sascha_lammers@gmx.de
#

class StructType(object):
    pass

class DictType(dict, StructType):
    def __init__(self, items={}):
        dict.__init__(self, items)

class RangeType(dict, StructType):
    def __init__(self, index, item_type, struct=DictType()):
        dict.__init__(self, {
            'range': index,
            'item_type': item_type,
            'struct': struct
        })

#
# Author: sascha_lammers@gmx.de
#

from . import *

class Loader(object):

    def __init__(self, config):
        if not isinstance(config, Base):
            raise TypeError('struct %s: ewxpected Base' % type_str(config))
        self._root = config
        self._create_struct(None, self._root, Root())

    def print_struct(self, obj=None):
        if obj==None:
            print('-- CONFIG STRUCT --')
            obj = self._root
        print("type=%s path=%s parent=%s struct=%s" % (Type.name(obj), obj.path(), Type.name(obj._parent), Type.name(obj._struct)))
        if hasattr(obj, '_children'):
            for child in obj._children:
                self.print_struct(child)

    # meta=True adds the type name as __type to the object
    def to_json(self, meta=False, obj=None):
        obj = obj!=None and obj or self._root
        json = {}
        if meta==True:
            json['__type'] = Type.name(obj)
        if hasattr(obj, '__getitem__'):
            items = []
            for child in obj._children:
                items.append(self.to_json(meta, child ))
            if meta==True:
                json['__items'] = items
                return json
            return items

        elif hasattr(obj, '_children'):
            for child in obj._children:
                json[str(child.path_name())] = self.to_json(meta, child)

        return json

    def load(self, filename):
        pass

        # print(Base._get('mqtt.hostname'))
        # Base._set('mqtt.hostname', '192.168.0.3')
        # print(Base._get('mqtt.hostname'))

    def _read_attr(self, obj):
        # print('_read_attr type=%s' % Type.name(obj))
        for name in dir(obj):
            if Path._is_key_valid(name):
                obj._add_param(name, Param.from_attr(obj, name))

    def _add_object(self, obj, parent, path):
        # print("_add_object %s path=<%s>%s" % (Type.name(obj), Type.name(parent), obj.path()))
        if self._root==None:
            self._root = obj
            obj._parent = parent
            obj._add_object(obj)
        else:
            obj._parent = parent
            parent._add_child(obj)
            self._root._add_object(obj)
        self._read_attr(obj)

    def _create_struct(self, name, config, parent):
        if isinstance(config, Param):
            # print('_add_param name=%s path=<%s>%s default=%s types=%s' % (name, Type.name(parent), parent._path + name, config.get_default(), config.get_types()))
            parent._add_param(name, config)
            return
        # print('_create_struct name=%s path=<%s>%s type=%s' % (name, Type.name(parent), config.path(), Type.name(config._struct)))
        if isinstance(config._struct, DictType):
            config._setup(parent._path + name)
            self._add_object(config, parent, config._path)
            for key, val in config._struct.items():
                self._create_struct(key, val, config)
        elif isinstance(config._struct, RangeType):
            config._setup(parent._path + name)
            self._add_object(config, parent, config._path)
            for index in config._struct['range']:
                item = config._struct['item_type'](config._struct['struct'])
                item._setup(config._path, index)
                self._add_object(item, config, item._path)

#
# Author: sascha_lammers@gmx.de
#

import glob
import sys
from os import path

def appdir_relpath(filename):
    app_dir = path.dirname(path.realpath(__file__))
    return path.realpath(path.join(app_dir, filename))

def get_mac_addresses():
    parts = []
    path = '/sys/class/net/'
    address = '/address'
    # exclude list
    exclude_ifnames = ['lo']
    for iface in glob.glob('%s*%s' % (path, address)):
        ifname = iface[len(path):-len(address)]
        if not ifname in exclude_ifnames:
            try:
                with open(iface, 'r') as f:
                    mac = f.readline().strip()
                    # skip any mac address that consists of zeros only
                    if mac.strip('0:')!='':
                        parts.append(mac)
            except:
                pass
    return parts

def get_bases(module, qualname, include_name=False, list=[]):
    class_type = getattr(sys.modules[module], qualname)
    for types in class_type.__bases__:
        if int.__module__!=types.__module__:
            if include_name:
                list.append((types.__module__, types.__qualname__, getattr(sys.modules[types.__module__], types.__name__)))
            else:
                list.append(getattr(sys.modules[types.__module__], types.__name__))
            get_bases(types.__module__, types.__qualname__, include_name, list)
    return list

# execute method of self on all bases
def execute_method(self_obj, classes, func_name, *args, **kwargs):
    for class_type in classes:
        if hasattr(class_type, func_name):
            func = getattr(class_type, func_name)
            if callable(func):
                func(self_obj, *args, **kwargs)


def EnumFromStr(cls, value, ignore_case=True,namespace=None):
    if isinstance(value, str):
        ts = value
        if isinstance(namespace, str):
            ts = '%s.%s' % (namespace, ts)
            namespace = True
        ts = ignore_case and ts.lower() or ts
        for i in cls:
            s = i.__str__()
            if ignore_case:
                s = s.lower()
            if namespace in(True, None) and s==ts:
                return i
            if namespace in(False, None) and s.split('.')[-1]==ts:
                return i
    return cls(value)

def EnumIncr(value):
    l = list(type(value))
    n = (int(value._value_) + 1) % len(l)
    return l[n]

def EnumDecr(value):
    l = list(type(value))
    n = (value._value_ - 1 + len(l)) % len(l)
    return l[n]


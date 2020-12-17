#
# Author: sascha_lammers@gmx.de
#

import glob
from os import path

def fround(val, n=1):
    if val < 0:
        return round(val - 0.000001, n)
    return round(val + 0.000001, n)

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

#
# Author: sascha_lammers@gmx.de
#

from .EventManager import (EVENT_MANAGER, EventData)
import copy
import threading

class Notification(object):
    def __init__(self, name, data, priority:int=EVENT_MANAGER.PRIORITY.NORMAL):
        if name==EVENT_MANAGER.THREAD.MULTIPLE:
            self._data = data
            self._id = None
        else:
            self._data = data
            self._id = id(self)
        self._name = name
        self._priority = priority
        self._event = None
        self._new_event = None
        self._handled = []

    def copy(self, name):
        clone = copy.deepcooy(self)
        clone._id = id(clone)
        clone._name = name
        return clone

    def remove(self):
        if self._event==None:
            raise RuntimeError('event is not attached')
        self._event.remove(self)

    def __copy__(self):
        raise RuntimeError('copy() not allowed')

    def __eq__(self, val):
        if val==None:
            return False
        if isinstance(val, str):
            return val==EVENT_MANAGER.THREAD.ANY or val==name
        elif isinstance(val, int):
            return val==self._id
        elif isinstance(val, Notification):
            return val._id==self._id
        raise TypeError('invalid type %s' % type(val))

    @property
    def data(self):
        return EventData(self._data)


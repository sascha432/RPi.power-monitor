#
# Author: sascha_lammers@gmx.de
#

from .Notification import Notification
from .EventManager import EVENT_MANAGER
import threading

class StopSleep(BaseException):
    def __init__(self, *args):
        BaseException.__init__(self, *args)

class Event(object):
    def __init__(self):
        self._event = threading.Event()
        self._notification_lock = threading.Lock()
        self._notifications = {}

    # add a notification for one thread or any listening
    def notify(self, notification: Notification):
        event = self._event
        with self._notification_lock:
            self._notify(notification)
            self._event = threading.Event()
        event.set()

    # notify multiple threads
    # set copy=True to create a deepcopy of the notification for each thread
    # the first one receives the original notification
    def multi_notify(self, names: tuple, notification:Notification):
        event = self._event
        with self._notification_lock:
            for name in names:
                self._notify(notification.copy(name))
            self._event = threading.Event()
        event.set()

    def dump(self):
        with self._notification_lock:
            for key, val in self._notifications.items():
                for item in val:
                    print('thread=%s id=%u data=%s' %(item._name, item._id, item._data))

    # methods for listeners

    def wait(self, timeout=None):
        return self._event.wait(timeout)

    def _get(self, listener):
        if not self._notification_lock.locked():
            raise RuntimeError('notifications not locked')
        if EVENT_MANAGER.THREAD.ANY in self._notifications:
            for item in self._notifications[EVENT_MANAGER.THREAD.ANY]:
                if not listener._name in item._handled:
                    return item
        if listener._name in self._notifications:
            return self._notifications[listener._name][-1]

    def _remove(self, listener, notification):
        if not self._notification_lock.locked():
            raise RuntimeError('notifications not locked')
        if notification._name==EVENT_MANAGER.THREAD.ANY:
            notification._handled.append(listener._name)
            return
        list = self._notifications[listener._name]
        idx = list.index(notification)
        if idx==None:
            raise KeyError('notification does not exist. id=%u thread=%s' % (notification._id, notification._name))
        del self._notifications[listener._name][idx]
        if len(self._notifications[listener._name])==0:
            del self._notifications[listener._name]

    def _notify(self, notification):
        if not self._notification_lock.locked():
            raise RuntimeError('notifications not locked')
        if not notification._name in self._notifications:
            self._notifications[notification._name] = []
        nlist = self._notifications[notification._name]
        nlist.append(notification)
        self._notifications[notification._name] = sorted(nlist, key=lambda item: item._priority, reverse=notification._name==EVENT_MANAGER.THREAD.ANY)

    def _set_event(self):
        if not self._notification_lock.locked():
            raise RuntimeError('notifications not locked')
        event = self._event
        self._event = threading.Event()
        event.set()

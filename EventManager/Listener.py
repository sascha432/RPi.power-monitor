#
# Author: sascha_lammers@gmx.de
#

from .Event import StopSleep
import time

class Listener(object):
    def __init__(self, name, event):
        self._event = event
        self._name = name

    # sleep and call handler if an event has been received
    #
    # time              time in seconds
    # handler           callable with Notification object as argument
    #                   raise StopSleep to skip the remaining sleep time after returning
    def sleep(self, sleep_time, handler):
        timeout = time.monotonic() + sleep_time
        try:
            while sleep_time>0:
                if not self._event.wait(sleep_time):
                    return
                notification = self.first()
                while notification!=None:
                    handler(notification)
                    notification = self.next(notification)
                sleep_time = timeout - time.monotonic()
        except StopSleep:
            pass

    # wait for a notification
    #
    # returns None after timeout or a Notification object
    # the event has to be removed with next() after processing
    def wait(self, wait_time):
        timeout = time.monotonic() + wait_time
        while wait_time>0:
            if not self._event.wait(wait_time):
                return
            notification = self.first()
            if notification!=None:
                return notification
            wait_time = timeout - time.monotonic()

    # get notification
    # use next() to remove this one and get the next one
    def first(self):
        with self._event._notification_lock:
            return self._event._get(self)

    # remove notification and return next
    # returns None or a new notification event from the queue
    def next(self, notification):
        with self._event._notification_lock:
            self._event._remove(self, notification)
            return self._event._get(self)

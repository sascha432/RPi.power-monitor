import EventManager
from EventManager.EventManager import EVENT_MANAGER
from pprint import pprint
import random
import sys
import threading
import time


e = EventManager.Event()


def handler(name, notification, state):
    print('thread=%s cmd=%s func=1' % (name, notification.data.cmd))
    if notification.data.cmd=='terminate':
        state['terminate'] = True
        raise EventManager.StopSleep

def thread_func1(name, event):
    listener = EventManager.Listener(name, event)
    state = {'terminate': False}
    while state['terminate']==False:
        print('alive1 %s' % name)
        listener.sleep(10.0, lambda notification: handler(name, notification, state))

def thread_func2(name, event):
    listener = EventManager.Listener(name, event)
    n=0
    while True:
        print('alive2 %s' % name)
        notification = listener.wait(10.0)
        while notification!=None:
            print('thread=%s cmd=%s func=2' % (name, notification.data.cmd))
            if notification.data.cmd=='terminate':
                return
            notification = listener.next(notification)




for n in range(10):
    r = random.randint(-5, 5)
    e.notify(EventManager.Notification('test1', {'cmd': 'hello %+02d' % r}, r))

t = []
thread = threading.Thread(target=thread_func1, args=('test1', e), daemon=True)
thread.start()
t.append(thread)
thread = threading.Thread(target=thread_func1, args=('test2', e), daemon=True)
thread.start()
t.append(thread)
thread = threading.Thread(target=thread_func2, args=('test3', e), daemon=True)
thread.start()
t.append(thread)

time.sleep(2)
e.notify(EventManager.Notification('test1', {'cmd': 'hello'}))

time.sleep(1)

for n in range(10):
    r = random.randint(-5, 5)
    e.notify(EventManager.Notification(EVENT_MANAGER.THREAD.ANY, {'cmd': 'hello %+02d' % r}, r))
    time.sleep(0.1)


time.sleep(1)

print('adding with lock')
with e._notification_lock:
    for n in range(10):
        r = random.randint(-5, 5)
        e._notify(EventManager.Notification('test1', {'cmd': 'hello %+02d' % r}, r))
        time.sleep(0.1)
    e._set_event()
    print('unlock')

time.sleep(2)

e.notify(EventManager.Notification(EVENT_MANAGER.THREAD.ANY, {'cmd': 'terminate'}))

for tt in t:
    tt.join()

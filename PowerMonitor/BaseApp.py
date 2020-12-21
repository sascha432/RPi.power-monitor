#
# Author: sascha_lammers@gmx.de
#

from . import PLOT_VISIBILITY, PLOT_PRIMARY_DISPLAY, ANIMATION, SCHEDULER_PRIO, DISPLAY_ENERGY
import EventManager
import threading
import time
import os
import signal
import sys
import sched
import enum

class Terminate:
    def __init__(self, event, terminate):
        self._event = event
        self._terminate = terminate
    def set(self):
        self._terminate.set()
        self._event.notify(EventManager.EVENT_MANAGER.THREAD.ANY, {'cmd': 'quit'})
    def is_set(self):
        return self._terminate.is_set()
    def wait(self, timeout):
        return self._terminate.wait(timeout)

class BaseApp(object):

    ENUMS = ()

    def __init__(self):
        global AppConfig
        AppConfig = self._app_config

        self._threads = []
        self._thread_idents = []
        # thread manager
        self._event = EventManager.Event()

        # data and plot locks
        self._data_lock = threading.Lock()
        self._plot_lock = threading.Lock()

        # lock for creating threads
        self.thread_lock = threading.Lock()

        self.start_time = time.monotonic()
        self.terminate = Terminate(self._event, threading.Event())
        AppConfig._terminate = self.terminate
        AppConfig._event = self._event

    def signal_handler_reload(self, signal, frame):
        self.info(__name__, 'SIGHUP received')
        self.reload_config()
        self.reload_gui()

    def signal_handler(self, signal, frame):
        self.debug(__name__, 'exiting, signal %u...', signal)
        self.terminate_app()

    # call from main thread only
    def terminate_app(self):
        self.terminate.set()
        self.debug(__name__, 'waiting for threads to terminate... %s' % self._thread_idents)
        timeout = time.monotonic() + 10
        count = 1
        while count>0:
            if time.monotonic()<timeout:
                self.info(__name__, 'PID %u ending' % os.getpid())
                break
            count = len(self._threads)
            for thread in self._threads:
                n = 0
                for thread in self._threads:
                    if thread.is_alive():
                        n += 1
                if thread.is_alive():
                    self.info(_name__, 'waiting for thread ident %s (%u left)' % (thread.ident % n))
                    thread.join(1)
                else:
                    count -= 1
        self.destroy()

        if AppConfig.daemon:
            file = AppConfig.get_filename(AppConfig.pid_file)
            os.unlink(file)

        self.quit()
        self.debug(__name__, 'exit(%s)', signal)
        sys.exit(signal)

    def init_signal_handler(self):
        if 'win' in sys.platform:
            handlers = (
                (self.signal_handler, (signal.SIGINT, signal.SIGTERM)),
                (self.signal_handler_reload, (),)
            )
        else:
            handlers = (
                (self.signal_handler, (signal.SIGINT, signal.SIGQUIT, signal.SIGABRT, signal.SIGTERM)),
                (self.signal_handler_reload, (signal.SIGHUP,))
            )

        for handler in handlers:
            for signum in handler[1]:
                try:
                    signal.signal(signum, handler[0])
                except Exception as e:
                    self.error(__name__, 'failed to install signal handler %u: %s', signum, e)

    def start(self):
        self.debug(__name__, 'start')
        self.info(__name__, 'starting')

    def init_vars(self):
        self.debug(__name__, 'init_vars')
        self._scheduler = sched.scheduler()

    def destroy(self):
        self.debug(__name__, 'destroy')
        self.info(__name__, 'shutting down')
        self.terminate.set();

    def quit(self):
        self.debug(__name__, 'quit')
        sys.exit(0)

    def thread_daemonize(self, name, target, args=(), sub='main'):
        name = '%s:%s' % (name, sub)
        thread = threading.Thread(target=target, args=args, daemon=True)
        thread.start()
        self.thread_lock.acquire()
        try:
            self._threads.append(thread)
            self.debug(__name__, 'daemonizing %s (%u)' % (name, len(self._threads)))
        finally:
            self.thread_lock.release()

    def get_thread_idents(self):
        pids = []
        for pid in self._thread_idents:
            pids.append(pid[1])
        return pids

    def thread_register(self, name, sub='main'):
        name = '%s:%s' % (name, sub)
        self.thread_lock.acquire()
        try:
            pid = threading.current_thread().ident
            self._thread_idents.append((name, pid))
            self.debug(__name__, 'adding thread %s ident %u (%u)' % (name, pid, len(self.get_thread_idents())))
        finally:
            self.thread_lock.release()

    def thread_unregister(self, name, sub='main'):
        name = '%s:%s' % (name, sub)
        self.thread_lock.acquire()
        try:
            index = 0
            for thread in self._thread_idents:
                if thread[0]==name:
                    self.debug(__name__, 'remove thread %s ident %u (%u)' % (thread[0], thread[1], len(self.get_thread_idents())))
                    del self._thread_idents[index]
                    break
                index += 1
        finally:
            self.thread_lock.release()

    def main_thread(self):
        self.thread_register(__name__)

        def ping():
            self.debug(__name__, 'ping main thread')
            self._scheduler.enter(60.0, SCHEDULER_PRIO.DEBUG_PING, ping)
        ping()

        try:
            while not self.terminate.is_set():
                self._scheduler.run(False)
                self.terminate.wait(0.25)
        except Exception as e:
            AppConfig._debug_exception(e)

        self.thread_unregister(__name__)

    def fork(self):
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except Exception as e:
            self.error('failed to fork: %s', e)

        os.chdir("/")
        os.setsid()
        os.umask(0)

        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)

        except Exception as e:
            self.error('failed to fork: %s', e)


    def daemonize(self, daemon):
        self.init_signal_handler()

        if daemon:
            self.debug(__name__, 'daemonizing...')
            self.fork()

            file = AppConfig.get_filename(AppConfig.pid_file)
            self.debug(__name__, 'creating PID file %s: %u' % (file, os.getpid()))
            with open(file, 'w') as f:
                f.write('%s\n' % os.getpid())

        if self._gui:
            self.thread_daemonize(__name__, self.main_thread, sub='daemon')
            # tk is the main thread with GUI
            self._gui.mainloop()
        else:
            self.main_thread()

    def _log_enabled(self, type, name):
        if type=='debug':
            if name in('xPowerMonitor.Mqtt'):
                return False
        return True

    def debug(self, name, msg, *args):
        if self._log_enabled('debug', name):
            self._logger.debug('[%s] %s' % (name, msg % args))

    def info(self, name, msg, *args):
        if self._log_enabled('info', name):
            self._logger.info('[%s] %s' % (name, msg % args))

    def warning(self, name, msg, *args):
        self._logger.warning('[%s] %s' % (name, msg % args))

    def error(self, name, msg, *args):
        self._logger.error('[%s] %s' % (name, msg % args))

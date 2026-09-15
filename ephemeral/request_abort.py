"""Request-owned transport interruption; stores no request or response content."""
import socket
import threading
import time

class RequestAbort:
    def __init__(self):
        self._lock = threading.Lock()
        self._finished = threading.Event()
        self._socket = None
        self._aborted = False
        self.expired = False
        self._armed = False

    def arm(self, deadline):
        with self._lock:
            if self._armed:
                raise RuntimeError('Request guard cannot be reused')
            self._armed = True
        def watch():
            if not self._finished.wait(max(0., deadline-time.monotonic())):
                self.abort(expired=True)
        threading.Thread(target=watch, daemon=True, name='ephemerai-deadline').start()

    def abort(self, *, expired=False):
        with self._lock:
            if self._finished.is_set():
                return
            self._aborted = True
            self.expired = self.expired or expired
            connection = self._socket
            self._finished.set()
            if connection is not None:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def trace(self, event, info):
        # httpcore's synchronous trace extension exposes the connected stream
        # before request headers/body are sent. Never retain info or its payloads.
        if event not in ('connection.connect_tcp.complete', 'connection.start_tls.complete'):
            return
        stream = info.get('return_value')
        connection = stream.get_extra_info('socket') if stream is not None else None
        if connection is None:
            raise RuntimeError('Request transport cannot support cancellation')
        with self._lock:
            if self._aborted or self._finished.is_set():
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                raise TimeoutError('Request no longer active')
            self._socket = connection

    def finish(self):
        with self._lock:
            self._finished.set()
            self._socket = None

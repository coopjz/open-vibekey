import queue
import threading
import time


class EventBus:
    def __init__(self):
        self.lock = threading.Lock()
        self.clients = set()
        self.sequence = 0

    def publish(self, kind, **data):
        with self.lock:
            self.sequence += 1
            event = dict(data, type=kind, id=self.sequence, time=time.time())
            for client in self.clients:
                try:
                    client.put_nowait(event)
                except queue.Full:
                    # Drop oldest, preserving bounded memory for slow browsers.
                    try:
                        client.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        client.put_nowait(event)
                    except queue.Full:
                        pass

    def subscribe(self):
        client = queue.Queue(maxsize=128)
        with self.lock:
            self.clients.add(client)
        return client

    def unsubscribe(self, client):
        with self.lock:
            self.clients.discard(client)

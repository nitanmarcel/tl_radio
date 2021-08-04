from collections import deque
from random import shuffle

class Queue:
    """Queue object used to manipulate a set of queued streams"""

    def __init__(self, ee, limit=None, loop=None):
        self._queue = deque(maxlen=limit)
        self._current_index = 0

        self._ee = ee

    def get(self, index=None):
        if index is None:
            index = self._current_index
        else:
            self._current_index = index
        if index < len(self._queue):
            return self._queue[index]

    def queue(self, stream, raise_event=True):
        self._queue.append(stream)
        if raise_event is True:
            self._dispatch_event()
        return stream

    def dequeue(self, index=0):
        if index < len(self._queue):
            stream = self._queue[index]
            self._queue.remove(self._queue[index])
            self._dispatch_event()
            return stream
        return None

    def clear(self):
        self._queue.clear()
        self._dispatch_event()

    def next(self, repeat_queue=False):
        if self._current_index + 1 < len(self._queue):
            self._current_index += 1
        elif repeat_queue is True:
            self._current_index = 0

    def prev(self, repeat_queue=False):
        if self._current_index > 0:
            self._current_index -= 1
            return True
        elif repeat_queue is True:
            self._current_index = len(self._queue) - 1
            return False

    def set(self, index=0):
        if index < len(self._queue):
            self._current_index = index
            return True
        return False

    def shuffle(self):
        playing = self.get()
        queue = [x for x in self._queue if x.id != playing.id]
        shuffle(queue)
        queue.insert(self._current_index, playing)
        self._queue = deque(queue)
        self._dispatch_event()

    def _dispatch_event(self):
        return self._ee.emit("event_queue_update", list(self._queue))

    @property
    def event(self):
        return self._ee

    @property
    def current_index(self):
        return self._current_index

    @property
    def length(self):
        return len(self.get_queue())

    def get_queue(self):
        return list(self._queue)

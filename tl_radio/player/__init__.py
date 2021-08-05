import asyncio
from typing import Union

from pyee import AsyncIOEventEmitter

from ._queue import Queue
from ._stream import Stream, RadioStream


class _RadioPlayer:
    """Radio player controller."""

    def __init__(self, ee, loop=None):
        self._loop = loop or asyncio.get_event_loop()
        self._ee = ee

        self._stream = None

    async def play(self, stream=None):
        await self.stop()
        self._stream = stream or self._stream
        await self._stream.start_stream()

    async def stop(self):
        if self._stream:
            self._stream.stop_stream(raise_event=False)

    @property
    def is_playing(self):
        if self._stream:
            return self._stream.is_streaming if self._stream else False

    @property
    def now_playing(self):
        return self._stream

    @now_playing.setter
    def now_playing(self, value):
        self._stream = value


class Player:
    """Stream player controller."""

    def __init__(self, max_queue_lenght=None, loop=None):
        self._loop = loop or asyncio.get_event_loop()
        self._ee = AsyncIOEventEmitter(loop=self._loop)

        self._queue: Queue = Queue(self._ee, max_queue_lenght)
        self._is_paused = False
        self._repeat_mode = 0

        self._radio_player = _RadioPlayer(self._ee, self._loop)

    async def add_to_queue(self, source: Union[RadioStream, Stream], raise_event=True):
        source.event = self._ee
        if isinstance(source, Stream):
            self._queue.queue(source, raise_event=raise_event)
        if isinstance(source, RadioStream):
            if self.is_playing:
                await self.stop()
            await self._radio_player.play(source)

    async def remove_from_queue(self, index=None):
        if index is None:
            self._queue.clear()
        stream = self._queue.get()
        deque = self._queue.dequeue(index)
        if deque:
            if stream.id == deque.id and not self._radio_player.is_playing:
                await self.stop()

    async def play(self):
        stream = self._queue.get()
        if stream:
            stream.loop = self._loop
            await self._radio_player.stop()
            self._radio_player.now_playing = None
            await stream.start_stream()

    async def play_next(self):
        if not self._radio_player.is_playing:
            await self.stop()
            self._queue.next(repeat_queue=self._repeat_mode == 2)
            await self.play()

    async def play_prev(self):
        if not self._radio_player.is_playing:
            await self.stop()
            if self._repeat_mode != 0:
                self._queue.prev(repeat_queue=self._repeat_mode == 2)
            await self.play()

    async def play_one(self, index=0):
        stream = self._queue.get(index)
        if stream and isinstance(stream, Stream):
            await self.stop()
            await self.play()

    async def pause(self):
        if not self._radio_player.is_playing:
            stream = self._queue.get()
        else:
            stream = self._radio_player.now_playing
        await self.stop()
        self._is_paused = True
        self._dispatch_event("event_playback_pause", stream)

    async def resume(self):
        if not self._radio_player.now_playing:
            stream = self._queue.get()
        else:
            stream = self._radio_player.now_playing
        if isinstance(stream, RadioStream):
            await self._radio_player.play()
        else:
            await self.play()

        self._is_paused = False
        self._dispatch_event("event_playback_resume", stream)

    async def stop(self):
        if not self._radio_player.is_playing:
            stream = self._queue.get()
        else:
            stream = self._radio_player.now_playing
        if stream:
            if isinstance(stream, RadioStream):
                await self._radio_player.stop()
                return
            stream.stop_stream(raise_event=False)

    def shuffle_queue(self):
        self._queue.shuffle()

    def read_buffer(self, _, length):
        if self._radio_player.now_playing:
            data = self._radio_player.now_playing.read(length)
            return data
        stream = self._queue.get()
        if stream:
            data = stream.read(length)
            return data

    @property
    def event(self):
        return self._ee

    @property
    def queue(self):
        return self._queue.get_queue()

    @property
    def repeat_mode(self):
        return self._repeat_mode

    @repeat_mode.setter
    def repeat_mode(self, value):
        if not self._radio_player.is_playing:
            self._repeat_mode = value

    @property
    def is_paused(self):
        return self._is_paused

    @property
    def is_playing(self):
        stream = self._queue.get()
        if stream is None:
            return self._radio_player.is_playing
        return stream.is_streaming or self._radio_player.is_playing

    @property
    def now_playing(self):
        return self._queue.get()

    @property
    def is_radio(self):
        return self._radio_player.is_playing

    def _dispatch_event(self, name, *args, **kwargs):
        self._ee.emit(name, *args, **kwargs)

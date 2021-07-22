import asyncio
import os
from urllib.request import urlopen

import ffmpeg

from . import events
from .station import Station
from ..utils.run_in_executor import run_in_executor


class Radio:
    def __init__(self, group_call):
        self._group_call = group_call
        self._handlers = []

        self._task = None
        self._station = None

    def get_station(self):
        return self._station

    async def play(self, url):
        station = await self._get_station(url)
        if not station:
            return
        self._station = station
        filename = "radio.raw"
        process = ffmpeg.input(url).output(filename, format="s16le",
                                           acodec="pcm_s16le",
                                           ac=2, ar="48k").overwrite_output()
        self._task = asyncio.create_task(run_in_executor(process.run, quiet=True))
        while not os.path.isfile(filename):
            await asyncio.sleep(1)
        self._group_call.input_filename = filename
        await self._trigger_event(events.EventRadioStarted, station)
        return station

    async def stop(self):
        if self.is_active:
            await self._group_call.stop()
            station = self._station
            filename = "radio.raw"
            if self._task:
                self._task.cancel()
            self._station = None
            await self._trigger_event(events.EventRadioStopped, station)
            if os.path.isfile(filename):
                os.remove(filename)

    @staticmethod
    async def _get_station(url):
        if not url.startswith("http"):
            url = "https://" + url
        try:
            _open = await run_in_executor(urlopen, url, timeout=100)
            _info = _open.info()
            if not _info.get_content_type():
                return None
            if _info.get_content_type().split("/")[0] == "audio":
                filename = url or _info.get_filename()
                return Station(url, filename)
        except TimeoutError:
            return None

    @property
    def is_active(self):
        return bool(self._station)

    def add_event_handler(self, event, callback):
        self._handlers.append({event: callback})

    def on(self, event):
        def decorator(func):
            self.add_event_handler(event, func)
            return func

        return decorator

    async def _trigger_event(self, event, *args, **kwargs):
        for handler in self._handlers:
            try:
                await handler[event](*args, **kwargs)
            except KeyError:
                pass

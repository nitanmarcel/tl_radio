import ffmpeg

from ..utils.run_in_executor import run_in_executor


class Stream:
    """Holds and controls information about the stream."""

    def __init__(self, id, url, title, extractor, duration):
        self.id = id
        self.url = url
        self.title = title
        self.extractor = extractor
        self.duration = duration

        self.data = None

        self._process = None
        self._streaming = False
        self._buffering = False
        self._ee = None

        self._loop = None

    async def start_stream(self):
        if self._process:
            self.stop_stream()
        process = ffmpeg.input(self.url).output("-", format="s16le", acodec="pcm_s16le", ac=2, ar="48k").global_args(
            "-loglevel", "fatal").global_args("-hide_banner")
        self._process = await run_in_executor(process.run_async, pipe_stdout=True)

    def stop_stream(self, raise_event=True):
        if self._process:
            self._process.kill()
            self._process = None
            if raise_event:
                self._dispatch_event("event_stream_end")
            self._streaming = False
            return True
        return False

    def read(self, length):
        if self._process is not None:
            if not self._process.stdout.closed:
                data = self._process.stdout.read(length)
                if self._streaming is False:
                    self._streaming = True
                    self._dispatch_event("event_stream_start")
                if self._process.poll() is not None and not data:
                    if self._streaming is True:
                        self._streaming = False
                        self._process.stdout.close()
                        self._dispatch_event("event_stream_end")
                    return None
                if self._process.poll() is None and not data:
                    if self._buffering is True:
                        self._buffering = False
                        self._dispatch_event("event_stream_start_buffering")
                        return None
                if self._process.poll() is None and data:
                    if self._buffering is True:
                        self._buffering = False
                        self._dispatch_event("event_stream_end_buffering")
                return data or None
        return None

    @property
    def is_streaming(self):
        return self._streaming

    @property
    def event(self):
        return self._ee

    @event.setter
    def event(self, ee):
        self._ee = ee

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, loop):
        self._loop = loop

    def _dispatch_event(self, name):
        self._ee.emit(name, self)


class RadioStream(Stream):
    """Same as Stream but represents a radio/live stream"""

    def __init__(self, id, url, title):
        super(RadioStream, self).__init__(id, url, title, None, None)



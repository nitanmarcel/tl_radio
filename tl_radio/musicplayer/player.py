import asyncio
import os

import ffmpeg
from youtube_dl import YoutubeDL, DownloadError

from tl_radio import CONFIG
from tl_radio.musicplayer.playlist import Playlist
from tl_radio.utils.run_in_executor import run_in_executor
from . import events

_ytdl_opts = {"format": "bestaudio/best",
              "extractaudio": True,
              "restrictfilenames": True,
              "noplaylist": True,
              "force_noplaylist": True,
              "playlistend": 1,
              "logtostderr": False,
              "no_color": True,
              "outtmpl": "%(id)s.%(ext)s",
              "source_address": "0.0.0.0",
              "postprocessors": [{"key": "FFmpegMetadata"}]}
_ytdl_opts.update(CONFIG.youtubedl_opts)
ytdl = YoutubeDL(_ytdl_opts)

playlist = Playlist()
semaphore = asyncio.Semaphore(CONFIG.general.active_downloads)


class Player:
    def __init__(self, group_call):
        self._group_call = group_call
        self._hanlders = []

    async def queue(self, song, url):
        if not os.path.isfile(song.file):
            async with semaphore:
                download = await run_in_executor(ytdl.extract_info, url)
                if download is None:
                    raise DownloadError(f"ERROR: Something went wrong while downloading: {url}")
                if "entries" in download.keys():
                    download = download["entries"][0]
                process = ffmpeg.input(f"{song.id}.{song.original_ext}").output(song.file, format="s16le",
                                                                                acodec="pcm_s16le",
                                                                                ac=2, ar="48k").overwrite_output()
                await run_in_executor(process.run, quiet=True)
                os.remove(f"{song.id}.{download['ext']}")
        playlist.add(song)
        await self._trigger_event(events.EventItemQueued, song)

    async def play(self, song=None):
        if not song:
            song = await playlist.get()
        if song:
            song = playlist.get(song_id=song.id)
            playlist.switch_now_playing()
            while not os.path.isfile(song.file):
                await asyncio.sleep(1)
            self._group_call.input_filename = song.file
            await self._trigger_event(events.EventPlaybackStarted, song)

    async def stop(self):
        await self._group_call.stop()
        playlist.clear()
        playlist.switch_now_playing()
        await self._trigger_event(events.EventPlaybackStopped)

    async def play_next(self):
        if self._group_call.is_connected:
            if playlist.is_empty:
                return
            queue = playlist.get_queue()
            if len(queue) < 2:
                return
            if os.path.isfile(queue[0].file) and len(queue) > 2 and queue[0].id not in [song.id for song in queue]:
                os.remove(queue[0].file)
            playlist.remove()
            while not os.path.isfile(queue[0].file):
                await asyncio.sleep(1)
            self._group_call.input_filename = queue[0].file
            await self._trigger_event(events.EventPlaybackStarted, queue[0])
            return queue[0]

    async def pause(self):
        self._group_call.pause_playout()
        await self._trigger_event(events.EventPlaybackPaused, playlist.get())

    async def resume(self):
        self._group_call.resume_playout()
        await self._trigger_event(events.EventPlaybackResumed, playlist.get())

    async def shuffle(self):
        playlist.shuffle()
        await self._trigger_event(events.EventPlaylistShuffled, playlist.get_queue())

    async def repeat(self):
        _repeat = playlist.switch_repeat()
        await self._trigger_event(events.EventRepeatToggled, _repeat)

    def add_event_handler(self, event, callback):
        self._hanlders.append({event: callback})

    def on(self, event):
        def decorator(func):
            self.add_event_handler(event, func)
            return func

        return decorator

    async def _trigger_event(self, event, *args, **kwargs):
        for handler in self._hanlders:
            try:
                await handler[event](*args, **kwargs)
            except KeyError:
                pass

    @property
    def is_on(self):
        return playlist.now_playing

    @property
    def ytdl_instance(self):
        return ytdl

    @property
    def playlist_instance(self):
        return playlist

    @property
    def group_call_instance(self):
        return self._group_call

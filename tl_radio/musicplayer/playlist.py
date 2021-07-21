from random import shuffle
from typing import List

from .song import Song


class Playlist:
    def __init__(self):
        self._songs: List[Song] = []
        self._play_next: bool = True
        self._now_playing = False

    def add(self, song: Song):
        self._songs.append(song)
        return self._songs

    def get(self, song_id=None):
        if self.is_empty:
            return
        if not song_id:
            return self._songs[0]
        return [s for s in self._songs if s.id == song_id][0]

    def remove(self, song: Song = None):
        if not song:
            self._songs.pop(0)
        else:
            self._songs = [s for s in self._songs if s.id != song.id]
        return self._songs

    def clear(self):
        self._now_playing = False
        self._songs.clear()

    def get_queue(self):
        return self._songs

    def switch_repeat(self):
        self._play_next = not self._play_next
        return not self._play_next

    def switch_now_playing(self):
        self._now_playing = not self._now_playing
        return self._now_playing

    def shuffle(self):
        if len(self._songs) > 2:
            songs = self._songs[1:]
            shuffle(songs)
            self._songs = self._songs[0] + songs
        return self._songs

    @property
    def is_empty(self):
        return not bool(self.count)

    @property
    def count(self):
        return len(self._songs)

    @property
    def repeat(self):
        return self._play_next

    @property
    def now_playing(self):
        return self._now_playing

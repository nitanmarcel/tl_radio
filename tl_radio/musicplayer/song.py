import os


class Song(object):
    id: str = None
    title: str = None
    duration: int = None
    original_ext: str = None
    file: str = None
    requested_by: str = None

    def __init__(self, _id: str, title: str, duration: int, original_ext, file: str, requested_by):
        self.id = _id
        self.title = title
        self.duration = duration
        self.original_ext = original_ext
        self.file = file
        self.requested_by = requested_by

    @property
    def downloaded(self):
        return os.path.isfile(self.file)

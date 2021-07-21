from sqlalchemy import Column, String, Integer

from . import BASE, SESSION
from ..utils.run_in_executor import make_async


class Cache(BASE):
    __tablename__ = "tl_radio_cache"

    query = Column(String(255), primary_key=True)
    title = Column(String(255))
    video_id = Column(String(255))
    ext = Column(String(255))
    extractor = Column(String(255))
    categories = Column(String(255))
    duration = Column(Integer)

    def __init__(self, query, title, video_id, ext, extractor, duration, categories=None):
        self.query = query
        self.title = title
        self.video_id = video_id
        self.ext = ext
        self.extractor = extractor
        self.duration = duration
        self.categories = categories


Cache.__table__.create(checkfirst=True)

SEARCH = {}


@make_async
def set_cache(query: str, title: str, video_id, ext, extractor: str, duration: int, categories=None):
    global SEARCH
    curr = SESSION.query(Cache).get(query)
    if not curr:
        categories = _parse_categories(categories)
        curr = Cache(query, title, video_id, ext, extractor, duration, categories)
        SESSION.add(curr)
        SESSION.commit()

        SEARCH[query] = {"title": title, "extractor": extractor, "id": video_id, "ext": ext, "duration": duration,
                         "categories": _parse_categories(categories)}
    return SEARCH[query]


def get_cache(query):
    return SEARCH[query]


def is_cached(query):
    return query in SEARCH.keys()


def _load_cache():
    global SEARCH
    try:
        _all = SESSION.query(Cache).all()
        for s in _all:
            SEARCH[s.query] = {"title": s.title, "extractor": s.extractor, "id": s.video_id, "ext": s.ext,
                               "duration": s.duration, "categories": _parse_categories(s.categories)}
    finally:
        SESSION.close()


def _parse_categories(cat):
    if isinstance(cat, list):
        return ",".join([str(x) for x in cat])
    return cat.split(",")


_load_cache()

from typing import Dict, Union, List, NoReturn
from urllib.request import urlopen

from youtube_dl.YoutubeDL import YoutubeDL
from youtube_dl.utils import ExtractorError, UnsupportedError

from ..utils.run_in_executor import run_in_executor
from validators import url as is_url, ValidationFailure


class YtDl:
    def __init__(self, ytld_args: dict):
        self._youtube_dl = YoutubeDL(ytld_args)

    async def extract_info(self, url: str) -> Union[List[Dict], NoReturn]:
        if not url.startswith("http"):
            if self.is_valid_url("http://" + url):
                url = "http://" + url
            else:
                url = "ytsearch:" + url

        info = await run_in_executor(self._youtube_dl.extract_info, url, download=False)
        is_radio_live = False

        if not info:
            raise ExtractorError(f"ERROR: Failed to extract data for: {url}", expected=True)
        if info["extractor"] == "generic":
            if not await self.is_radio(info["url"]):
                raise UnsupportedError(url)
            else:
                is_radio_live = True

        elif "entries" in info.keys():
            results = []
            for entry in info["entries"]:
                results.append(
                    {
                        "id": entry.get("id"),
                        "title": entry.get("title", url),
                        "url": entry.get("url"),
                        "extractor": entry["extractor"],
                        "duration": entry.get("duration", 0) if not entry.get("is_live", False) else -1,
                        "categories": info.get("categories", ["Live"]),
                        "is_live": info.get("is_live", is_radio_live)
                    }
                )
                if info["extractor"].split(":", 1)[-1].lower() == "search":
                    break
            return results

        return [
            {
                "id": info.get("id"),
                "title": info.get("title", url),
                "url": info.get("url"),
                "extractor": info["extractor"] if not info["extractor"] == "generic" else "live",
                "duration": info.get("duration", 0) if not info.get("is_live", False) else -1,
                "categories": info.get("categories", ["Live"]),
                "is_live": info.get("is_live", is_radio_live)
            }
        ]

    @staticmethod
    async def is_radio(url) -> bool:
        try:
            _open = await run_in_executor(urlopen, url, timeout=5)
            _info = _open.info()
            _content_type = _info.get_content_type()
            if not _content_type:
                return False
            return _content_type.split("/")[0] == "audio"
        except TimeoutError:
            return False

    @staticmethod
    def is_valid_url(url) -> bool:
        try:
            return is_url(url)
        except ValidationFailure:
            return False

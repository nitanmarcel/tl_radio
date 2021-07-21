from dataclasses import dataclass, field
from typing import Dict

from .general import General
from .telegram import Telegram


@dataclass
class BaseConfig:
    telegram: Telegram = Telegram
    general: General = General
    youtubedl_opts: Dict = field(default_factory=dict())

from dataclasses import dataclass
from typing import Optional


@dataclass
class Telegram:
    api_id: int
    api_hash: str
    bot_token: Optional[str] = None

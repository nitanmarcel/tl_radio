from dataclasses import dataclass, field
from typing import List


@dataclass
class General:
    sqlalchemy_db_uri: str
    cmd_prefix: str = "/"
    autojoin: bool = False
    active_downloads: int = 0
    anonymous: bool = False
    enforce_admin: bool = True
    exceptions: List[int] = field(default_factory=[00000000, ])

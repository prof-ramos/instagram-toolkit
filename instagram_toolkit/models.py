"""
Modelos canônicos de domínio do toolkit.
Isola o código da dependência direta nos tipos da instagrapi.
"""

from dataclasses import dataclass
from typing import TypedDict


@dataclass(frozen=True)
class UserRecord:
    """Modelo canônico de usuário do domínio."""
    pk: int
    username: str
    full_name: str
    is_private: bool
    is_verified: bool

    @classmethod
    def from_instagrapi(cls, pk: int, user: object) -> "UserRecord":
        return cls(
            pk=pk,
            username=getattr(user, "username", ""),
            full_name=getattr(user, "full_name", ""),
            is_private=getattr(user, "is_private", False),
            is_verified=getattr(user, "is_verified", False),
        )


class FollowerData(TypedDict):
    id: str
    username: str
    full_name: str
    is_private: bool
    is_verified: bool


class GrowthStats(TypedDict):
    period_days: int
    start_count: int
    end_count: int
    change: int
    daily_average: float
    start_date: str
    end_date: str


@dataclass
class TrackerResult:
    is_first_run: bool
    backup_path: object  # Path
    unfollowed: set[str]
    new_followers: set[str]
    history: dict[str, str]
    current_data: dict[str, str]

"""
Modelos canônicos de domínio do toolkit.
Isola o código da dependência direta nos tipos da instagrapi.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict


@dataclass(frozen=True)
class UserRecord:
    """Modelo canônico de usuário do domínio."""
    pk: int
    username: str
    full_name: str
    is_private: bool
    is_verified: bool
    follower_count: int = 0
    following_count: int = 0
    media_count: int = 0
    biography: str = ""
    external_url: str | None = None

    @classmethod
    def from_instagrapi(cls, pk: int, user: Any) -> UserRecord:
        return cls(
            pk=pk,
            username=getattr(user, "username", ""),
            full_name=getattr(user, "full_name", ""),
            is_private=getattr(user, "is_private", False),
            is_verified=getattr(user, "is_verified", False),
            follower_count=getattr(user, "follower_count", 0),
            following_count=getattr(user, "following_count", 0),
            media_count=getattr(user, "media_count", 0),
            biography=getattr(user, "biography", ""),
            external_url=getattr(user, "external_url", None),
        )


class FollowerData(TypedDict, total=False):
    id: str
    username: str
    full_name: str
    is_private: bool
    is_verified: bool
    follower_count: int
    following_count: int
    media_count: int
    biography: str
    external_url: str | None


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
    backup_path: Path
    unfollowed: set[str]
    new_followers: set[str]
    history: dict[str, str]
    current_data: dict[str, str]

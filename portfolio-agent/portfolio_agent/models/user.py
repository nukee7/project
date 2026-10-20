"""User model for authentication."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class User:
    """A registered user of the system."""

    user_id: str
    email: str
    name: str
    password_hash: str               # bcrypt hash, never store plain text
    created_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True

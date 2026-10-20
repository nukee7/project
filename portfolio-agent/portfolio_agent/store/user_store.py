"""In-memory user store. Replace with a database for production."""

from __future__ import annotations

import uuid

from portfolio_agent.models.user import User
from portfolio_agent.auth.passwords import hash_password, verify_password


class UserStore:
    """In-memory user storage with sign-up and sign-in."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}          # user_id → User
        self._email_index: dict[str, str] = {}      # email → user_id

    def sign_up(self, email: str, name: str, password: str) -> User:
        """Register a new user. Raises ValueError if email exists."""
        email_lower = email.lower().strip()
        if email_lower in self._email_index:
            raise ValueError(f"Email '{email_lower}' is already registered")

        user_id = uuid.uuid4().hex[:12]
        user = User(
            user_id=user_id,
            email=email_lower,
            name=name.strip(),
            password_hash=hash_password(password),
        )
        self._users[user_id] = user
        self._email_index[email_lower] = user_id
        return user

    def sign_in(self, email: str, password: str) -> User | None:
        """Authenticate a user. Returns User or None if invalid."""
        email_lower = email.lower().strip()
        user_id = self._email_index.get(email_lower)
        if not user_id:
            return None
        user = self._users.get(user_id)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def get_user(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        uid = self._email_index.get(email.lower().strip())
        return self._users.get(uid) if uid else None

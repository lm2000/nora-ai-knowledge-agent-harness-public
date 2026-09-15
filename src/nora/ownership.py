"""Global thread ownership claims across role runtimes.

A client-visible thread id is owned by the first role runtime that claims it.
Subsequent attempts by a different role to ask, read, resume, or export the
same id are denied.  Legacy un-namespaced Knowledge checkpoints are treated as
Knowledge-owned when first accessed.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from nora.config import ConfigurationError
from nora.roles import valid_role


class OwnershipStore(ABC):
    """Claim and query the owning role for a client-visible thread id."""

    @abstractmethod
    async def claim(self, thread_id: str, role: str) -> tuple[bool, str]:
        """Try to claim thread_id for role.

        Returns (accepted, owner).  accepted is True when the caller won or
        already owns the claim; owner is the current owner after the call.
        """

    @abstractmethod
    async def owner(self, thread_id: str) -> str | None:
        """Return the owning role, or None if the id has never been claimed."""


@dataclass
class InMemoryOwnershipStore(OwnershipStore):
    """Process-local ownership store for tests and single-process runtimes."""

    _claims: dict[str, str] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def claim(self, thread_id: str, role: str) -> tuple[bool, str]:
        if not valid_role(role):
            raise ConfigurationError(f"Invalid role: {role}")
        async with self._lock:
            owner = self._claims.get(thread_id)
            if owner is None:
                self._claims[thread_id] = role
                return True, role
            return owner == role, owner

    async def owner(self, thread_id: str) -> str | None:
        return self._claims.get(thread_id)


class PostgresOwnershipStore(OwnershipStore):
    """Persistent ownership store backed by the shared PostgreSQL database."""

    def __init__(self, conninfo: str):
        self.conninfo = conninfo

    async def setup(self) -> None:
        """Create the ownership table if it does not exist."""
        import psycopg

        async with await psycopg.AsyncConnection.connect(self.conninfo) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS nora_thread_ownership (
                        thread_id TEXT PRIMARY KEY,
                        role TEXT NOT NULL,
                        claimed_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )
            await conn.commit()

    async def claim(self, thread_id: str, role: str) -> tuple[bool, str]:
        if not valid_role(role):
            raise ConfigurationError(f"Invalid role: {role}")
        import psycopg

        async with await psycopg.AsyncConnection.connect(self.conninfo) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO nora_thread_ownership (thread_id, role)
                    VALUES (%s, %s)
                    ON CONFLICT (thread_id) DO UPDATE SET role = nora_thread_ownership.role
                    RETURNING role
                    """,
                    (thread_id, role),
                )
                row = await cursor.fetchone()
            await conn.commit()
        owner = row[0]
        return owner == role, owner

    async def owner(self, thread_id: str) -> str | None:
        import psycopg

        async with await psycopg.AsyncConnection.connect(self.conninfo) as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT role FROM nora_thread_ownership WHERE thread_id = %s",
                    (thread_id,),
                )
                row = await cursor.fetchone()
        return row[0] if row else None

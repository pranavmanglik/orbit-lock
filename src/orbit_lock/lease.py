# Copyright 2026-present Orbit Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Safe provider-neutral expiring leases with mandatory fencing tokens."""

from __future__ import annotations

import asyncio
from typing import Protocol, runtime_checkable

_MAX_RESOURCE_LENGTH = 256
_MIN_TTL_MS = 100
_MAX_TTL_MS = 86_400_000


class LockOperationError(Exception):
    """A lock provider failed without exposing resource names or credentials."""


class LockClosedError(LockOperationError):
    """The provider has started or completed shutdown."""


class LeaseLostError(LockOperationError):
    """The lease is expired, released, or no longer owned by this caller."""


class _LeaseBackend(Protocol):
    """Provider operations used by a lease handle."""

    async def renew_lease(self, resource: str, owner: bytes, ttl_ms: int) -> bool:
        """Extend a lease only when its owner token still matches."""

    async def release_lease(self, resource: str, owner: bytes) -> bool:
        """Release only a lease still owned by this handle."""


@runtime_checkable
class LockProvider(Protocol):
    """Non-blocking lock acquisition with explicit TTL and a fencing token."""

    async def try_acquire(self, resource: str, *, ttl_ms: int) -> LockLease | None:
        """Acquire immediately or return ``None`` when another owner holds the lease."""

    async def aclose(self) -> None:
        """Close provider resources after application-owned leases are released."""


class LockLease:
    """One bounded lease handle; its owner secret and resource are hidden from repr."""

    __slots__ = (
        "_backend",
        "_resource",
        "_owner",
        "_guard",
        "_released",
        "_fencing_token",
    )

    def __init__(
        self, backend: _LeaseBackend, resource: str, owner: bytes, fencing_token: int
    ) -> None:
        """Create a lease; provider implementations should construct this after atomic acquire."""
        if (
            not isinstance(fencing_token, int)
            or isinstance(fencing_token, bool)
            or fencing_token < 1
        ):
            raise ValueError("fencing_token must be a positive integer.")
        validate_resource(resource)
        if not isinstance(owner, bytes) or len(owner) != 32:
            raise ValueError("owner must be a 32-byte secret token.")
        self._backend = backend
        self._resource = resource
        self._owner = owner
        self._guard = asyncio.Lock()
        self._released = False
        self._fencing_token = fencing_token

    @property
    def fencing_token(self) -> int:
        """Return the immutable token assigned to this acquisition."""
        return self._fencing_token

    async def renew(self, *, ttl_ms: int) -> None:
        """Extend the lease if it remains owned; report loss rather than imply protection."""
        _validate_ttl(ttl_ms)
        async with self._guard:
            if self._released:
                raise LeaseLostError("Lock lease is no longer owned.")
            try:
                renewed = await self._backend.renew_lease(self._resource, self._owner, ttl_ms)
            except asyncio.CancelledError:
                raise
            except LockOperationError:
                raise
            except Exception:
                raise LockOperationError("Lock lease renewal failed.") from None
            if not renewed:
                self._released = True
                raise LeaseLostError("Lock lease is no longer owned.")

    async def release(self) -> None:
        """Release once, using compare-and-delete semantics supplied by the provider."""
        async with self._guard:
            if self._released:
                return
            try:
                await self._backend.release_lease(self._resource, self._owner)
            except asyncio.CancelledError:
                raise
            except LockOperationError:
                raise
            except Exception:
                raise LockOperationError("Lock lease release failed.") from None
            self._released = True

    async def __aenter__(self) -> LockLease:
        """Enter a context without altering the lease duration."""
        if self._released:
            raise LeaseLostError("Lock lease is no longer owned.")
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Release the lease on context exit."""
        await self.release()

    def __repr__(self) -> str:
        """Show only the fencing token, never the protected resource or owner secret."""
        return f"LockLease(fencing_token={self.fencing_token}, released={self._released})"


def validate_resource(resource: str) -> str:
    """Validate and return a bounded resource name without normalizing its identity."""
    if not isinstance(resource, str) or not resource or len(resource) > _MAX_RESOURCE_LENGTH:
        raise ValueError("resource must be a non-empty string of at most 256 characters.")
    if resource.strip() != resource or any(ord(character) < 32 for character in resource):
        raise ValueError("resource must not contain surrounding whitespace or control characters.")
    return resource


def validate_ttl(ttl_ms: int) -> int:
    """Validate lease TTL in milliseconds and return it unchanged."""
    if not isinstance(ttl_ms, int) or isinstance(ttl_ms, bool):
        raise ValueError("ttl_ms must be an integer.")
    _validate_ttl(ttl_ms)
    return ttl_ms


def _validate_ttl(ttl_ms: int) -> None:
    """Reject invalid TTL values before they reach a backend."""
    if (
        not isinstance(ttl_ms, int)
        or isinstance(ttl_ms, bool)
        or not _MIN_TTL_MS <= ttl_ms <= _MAX_TTL_MS
    ):
        raise ValueError("ttl_ms must be an integer between 100 and 86400000.")

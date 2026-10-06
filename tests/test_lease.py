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
from __future__ import annotations

import asyncio

import pytest

from orbit_lock import LeaseLostError, LockLease


class FakeBackend:
    def __init__(self) -> None:
        self.renew_result = True
        self.release_result = True
        self.renew_calls: list[tuple[str, bytes, int]] = []
        self.release_calls: list[tuple[str, bytes]] = []

    async def renew_lease(self, resource: str, owner: bytes, ttl_ms: int) -> bool:
        self.renew_calls.append((resource, owner, ttl_ms))
        return self.renew_result

    async def release_lease(self, resource: str, owner: bytes) -> bool:
        self.release_calls.append((resource, owner))
        return self.release_result


def lease(backend: FakeBackend) -> LockLease:
    return LockLease(backend, "resource:1", b"x" * 32, 17)


@pytest.mark.asyncio
async def test_renew_and_release_use_the_owner_and_bounded_ttl() -> None:
    backend = FakeBackend()
    handle = lease(backend)

    await handle.renew(ttl_ms=400)
    await handle.release()
    await handle.release()

    assert backend.renew_calls == [("resource:1", b"x" * 32, 400)]
    assert backend.release_calls == [("resource:1", b"x" * 32)]


@pytest.mark.asyncio
async def test_lease_lost_on_failed_renewal_and_does_not_release_again() -> None:
    backend = FakeBackend()
    backend.renew_result = False
    handle = lease(backend)

    with pytest.raises(LeaseLostError):
        await handle.renew(ttl_ms=400)
    with pytest.raises(LeaseLostError):
        await handle.renew(ttl_ms=400)
    await handle.release()

    assert backend.release_calls == []


@pytest.mark.asyncio
async def test_context_exit_releases_and_repr_hides_resource_and_owner() -> None:
    backend = FakeBackend()
    handle = LockLease(backend, "private-resource", b"s" * 32, 9)

    async with handle:
        assert handle.fencing_token == 9

    assert "private-resource" not in repr(handle)
    assert "s" * 32 not in repr(handle)
    assert len(backend.release_calls) == 1


def test_fencing_token_is_immutable() -> None:
    handle = lease(FakeBackend())
    with pytest.raises(AttributeError):
        handle.fencing_token = 18  # type: ignore[misc]


@pytest.mark.parametrize("ttl_ms", [True, 0, 99, 86_400_001, 1.5])
def test_renew_rejects_invalid_ttl(ttl_ms: object) -> None:
    with pytest.raises(ValueError):
        asyncio.run(lease(FakeBackend()).renew(ttl_ms=ttl_ms))  # type: ignore[arg-type]


@pytest.mark.parametrize("resource", ["", " x", "x ", "x\n", "x" * 257])
def test_lease_rejects_invalid_resource(resource: str) -> None:
    with pytest.raises(ValueError):
        LockLease(FakeBackend(), resource, b"x" * 32, 1)


def test_constructor_rejects_invalid_fencing_token() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        LockLease(FakeBackend(), "resource", b"x" * 32, 0)

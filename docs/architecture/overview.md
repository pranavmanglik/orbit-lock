# Orbit Lock: architecture and boundaries

## Responsibility

`orbit-lock` defines a provider-neutral asynchronous lease contract. Install a provider adapter
separately to use leases:

```bash
python -m pip install orbit-lock
```

Providers expose `LockProvider.try_acquire(resource, ttl_ms=...)`. Acquisition is non-blocking and
returns `None` when the lease is currently held. Every lease carries a strictly positive fencing
token, can be renewed, and should be released with `release()` or an async context manager. Resource
names are bounded and omitted from lease representations. TTLs are 100 ms to 24 hours; applications
must choose values that account for pauses, network delay, and operation duration.

```python
lease = await provider.try_acquire("invoice:42", ttl_ms=30_000)
if lease is None:
    return
async with lease:
    # Pass lease.fencing_token to protected storage and reject stale tokens there.
    await update_invoice(fencing_token=lease.fencing_token)
```

Leases are time-limited coordination, not proof that a process still owns a resource. A paused
client can resume after expiry. Protected storage must atomically reject stale fencing tokens for
the lock to guard writes safely. Lease renewal does not happen automatically; callers must schedule
it and stop protected work when renewal raises `LeaseLostError`. Cancellation propagates from
provider calls. Applications own provider shutdown and should release active leases before closing
the provider.
If cancellation or a transport failure interrupts acquisition after the backend commits it, the
caller may not receive the lease handle; the backend TTL bounds that orphaned lease. Keep TTLs
appropriate for the work and make protected operations safe against retries.

The capability package has no database, Redis dependency, local fake lock, or implicit polling
loop. See `orbit-cache-redis[lock]` for the optional Redis adapter and its topology-specific limitations.
This package is pre-alpha and its public API is not stable.

## Declared dependencies

The following dependency declarations come from the checked-in manifests. Optional groups and development dependencies are called out separately.

### `pyproject.toml`
- No dependencies declared.
- Optional `dev` group: `pytest>=8,<10`, `pytest-asyncio>=0.24,<2`, `ruff>=0.8,<1`, `mypy>=1.13,<2`.

Declared dependencies do not mean that optional providers or services are bundled with this package.

## Implementation layout

Representative implementation files in this checkout:

- `src/orbit_lock/__init__.py`
- `src/orbit_lock/lease.py`

## Public contract and scope

The README does not contain a separately headed architecture section. Its responsibility statement above and the public source files define the implemented scope; this guide adds no behavior beyond that description.

## Boundary rules

Keep provider SDKs, credentials, transports, and provider-specific error translation in provider adapters. Keep reusable capability contracts in the matching capability package and lifecycle orchestration in Core. Apply the relevant layer for this repository and preserve the dependency direction shown above.

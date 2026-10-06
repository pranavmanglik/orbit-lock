# Orbit Lock

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

## Documentation

The package-specific guides cover [architecture](docs/architecture/overview.md), [operations and security](docs/operations/README.md), and [development](docs/development/README.md), with [security guidance](docs/security/overview.md). The [documentation index](docs/README.md) links to the full package overview and project policies.

## Development

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
mypy
```

Licensed under Apache-2.0.


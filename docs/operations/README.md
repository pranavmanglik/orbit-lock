# Orbit Lock: operations and security

This guide organizes runtime behavior documented by the package. It does not certify production readiness. Verify provider/client versions, permissions, transport security, limits, and failure behavior in the target environment before release.

## Configuration surface

Environment names found in the package README:

The package README does not name `ORBIT_*` variables. Use its typed constructors and application configuration, and confirm exact runtime inputs in the implementation before deployment.

Use the package README's constructor and deployment examples. Store credentials in a secret manager and avoid logging credentials, raw provider errors, request data, or opaque cursors.

## Lifecycle, failure behavior, and limits

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

## Production validation

Validate startup/shutdown cleanup, timeout and cancellation behavior, concurrency and payload bounds where applicable, secret rotation and least-privilege access, data durability, backup/restore, and failover against the selected provider. Do not infer distributed or durable guarantees from an in-process API or fake-client tests.

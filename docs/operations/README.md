# Operations

`orbit-lock` defines lease handles and a provider interface. It does not connect to a lock service,
start renewal jobs, track active handles, or close an application provider automatically. The
application owns those lifecycle decisions.

## Acquire and use a lease

`try_acquire(resource, ttl_ms=...)` is non-blocking: `None` means the provider reports a current
holder. A returned `LockLease` includes a positive fencing token. Use a context manager for prompt
release, and pass the fencing token to the system that performs the protected write:

```python
lease = await provider.try_acquire("invoice:42", ttl_ms=30_000)
if lease is None:
    return
async with lease:
    await invoices.apply_if_fencing_token_is_newer(
        invoice_id="42", fencing_token=lease.fencing_token
    )
```

The destination must atomically remember and reject tokens older than the latest accepted token
for that resource. Without that destination-side check, a process paused past lease expiry can wake
up and perform a stale write. A lock alone cannot prevent this. The adapter must issue tokens that
increase monotonically for each resource across all owners and survive the failure modes of its
backend; a merely positive random token does not provide fencing.

## Renewal and failure handling

The lease does not renew itself. If work may outlast its TTL, the caller must schedule renewals and
coordinate them with cancellation and work completion. Stop protected work immediately when
`renew()` raises `LeaseLostError`. A provider exception becomes a sanitized `LockOperationError`
unless the provider already raised a typed lock error; cancellation propagates to the caller. Do
not treat a renewal network timeout as proof the lease is still held.

TTL values are integers from 100 through 86,400,000 milliseconds. Choose a TTL with margin for
runtime pauses, scheduling delay, and provider latency. Keep protected operations idempotent or
fencing-safe because a lost response can make acquisition or release outcome ambiguous. If
acquisition commits remotely but its response is cancelled or lost, no handle is available to
release; backend expiry bounds that orphaned lease.

## Shutdown and deployment

Stop new work first, cancel and await work tasks, release held leases, then close the provider
through its documented `aclose()` method. The capability has no active-lease registry, so it cannot
enforce this order. A failed release is surfaced and may leave the lease until expiry. Configure
provider timeouts and application shutdown deadlines so cleanup cannot hang indefinitely.

The Redis implementation is provided by `orbit-cache-redis[lock]`; consult that adapter's guide
for its Redis topology, durability, and failover limitations. This package itself has no Redis
dependency or local lock implementation. Validate failover, partitions, expiry behavior, fencing
monotonicity, cancellation, and concurrent acquisition against a dedicated service before rollout.
Unit tests with an in-memory fake do not establish distributed correctness.

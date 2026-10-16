# Architecture and contract

## Package boundary

`orbit-lock` is the provider-neutral Python capability for expiring leases. It validates resource
names and TTLs, defines structural protocols, and supplies a handle that serializes renewal and
release calls. It does not provide a backend, persistence, retry policy, renewal scheduler,
distributed coordination algorithm, or application lifecycle integration.

```text
Orbit application
  ├── owns task supervision, work cancellation, and provider lifecycle
  ├── uses LockProvider.try_acquire(resource, ttl_ms)
  └── passes LockLease.fencing_token to protected storage
        └── atomically rejects stale tokens

orbit-lock capability
  ├── LockProvider protocol
  ├── LockLease lifecycle and sanitized errors
  └── input validation

provider adapter
  ├── backend SDK and transport
  ├── atomic acquisition and owner comparison
  └── durable per-resource fencing token generation
```

The `orbit-cache-redis[lock]` adapter implements the contract for Redis. It remains an optional
distribution and owns Redis-specific dependencies, settings, credentials, failure translation,
and lifecycle. Applications should depend on the capability and the chosen adapter explicitly.

## Lease state

An acquisition has a backend resource key, an owner secret, an expiry, and a positive fencing
token. `renew()` extends the expiry only if the backend still recognizes the same owner. A false
renewal result marks the handle lost and raises `LeaseLostError`. `release()` is idempotent at the
handle level and asks the provider to compare the owner before deleting the lease. Concurrent
renew/release calls on one handle are serialized.

The handle does not own a background task. The caller schedules renewal if required, stops work
when ownership is uncertain, and releases the lease before provider shutdown. If a remote request
commits but its response is lost, the client may not know the outcome; backend TTL bounds an
acquisition without a returned handle.

## Fencing is enforced by the destination

The lock service cannot stop an expired owner from resuming. The protected storage system must
atomically compare the supplied token with the latest accepted token for that resource and reject
older values. Adapters must issue monotonic per-resource tokens across ownership changes and
supported failover. This package can check that a token is positive, but cannot prove monotonicity
or destination enforcement.

## Public modules

- `orbit_lock.LockProvider`: provider contract for non-blocking acquisition and async close.
- `orbit_lock.LockLease`: renew, release, context management, and fencing token access.
- `orbit_lock.LeaseLostError`: ownership is no longer confirmed.
- `orbit_lock.LockOperationError`: sanitized backend operation failure.
- `orbit_lock.validate_resource` / `validate_ttl`: reusable input validation.

Keep provider SDKs and provider configuration out of this package. Keep application readiness,
workload retries, lock renewal scheduling, and fenced writes in the application or its relevant
capability integration.

# Security

## Coordination limits

A lease is a time-bounded coordination signal. It is not a process identity, a durable mutex, or
proof that a caller still owns a resource. Clock behavior, pauses, partitions, provider failover,
and delayed responses can cause two clients to believe they may proceed. Use fencing tokens and
make the protected storage atomically reject stale tokens. If the protected system cannot enforce
fencing, do not rely on this lease to prevent stale writes.

The adapter must ensure each fencing token is strictly greater than every token previously issued
for the same resource, including after restart and supported failover. Document the provider's
counter durability and scope. Positive tokens alone are insufficient. Review Redis replication,
restore, failover, and split-brain behavior in the specific adapter documentation.

## Sensitive values

Resource names and owner tokens are omitted from `LockLease` representations, and provider errors
are replaced with generic messages unless already typed. This is not a guarantee against logging
inside an adapter, instrumentation hooks, memory inspection, or tracing. Avoid placing personal or
secret data in resource names, and never emit owner tokens or backend credentials in logs. Keep
provider credentials in workload identity or a secret manager with least-privilege access.

## Adapter requirements

Provider implementations should acquire atomically, use an unguessable per-acquisition owner
secret, compare that owner during renewal and release, use server-side expiry, and avoid exposing
raw backend errors that contain endpoints or credentials. Use authenticated encrypted transport,
verify TLS certificates, set bounded timeouts, and document topology-specific durability and
failover behavior. Cancellation and ambiguous timeouts must not cause a caller to assume ownership.

## Vulnerability reporting

Report suspected vulnerabilities using the private process in the repository's
[security policy](../../SECURITY.md). Avoid public exploit details while maintainers investigate.

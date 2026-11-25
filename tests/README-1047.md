# Event-driven native test contracts (#1047)

This cleanup changes tests only. It does not restore the withdrawn universal
application hold, execution-drain dispatcher, scope-mutation protocol, observation
census, or their signed v2 coverage grammar. Historical protocol documents under
`shared/` remain historical; no test negotiates those protocols as current APIs.

## Retired actors and their current coverage

| Removed test contract | Current assertions retained |
| --- | --- |
| `test_mutation_coverage_runtime.py` / `test_mutation_coverage_wire.py` and v2 producer fixture | Event v1 HMAC/schema vectors stay in `test_mutation_wire.py`; exact request signatures and phases stay in backend, public-source and projected-source actors. Ordinary in-flight/missing-receipt requests do not gate complete HITs in `test_event_invalidation_runtime.py`. Actual owner writes still invalidate only their dependency. |
| `test_execution_drain_runtime.py` / `test_execution_drain_wire.py` and dispatcher fixture | The removed dispatcher has no current completion authority. Metadata retry/decline/exhaustion, exact original ownership, no cookie replay and actual fragment expiry remain in `test_reuse_full_runtime.py`. Signed delivery context, phase/URL authentication and invalid candidate rejection remain in `test_reuse_delivery_context.py`, `test_delivery_authorization.py` and native codec tests. |
| `test_scope_mutation.py` / `test_authority_recovery_revision.py` | Supported tag BEGIN/COMMIT/ACK, overlapping real writers, delayed replay rejection, policy/epoch replacement, scope isolation, authentication and explicit generation publication remain in `test_reuse_authority.py`. Removed scope-writer/whole-scope RNG-fault fixtures are retired, not silently represented as current tag tests. |
| Held-reader branches in `test_reuse_full_runtime.py` | Complete mixed personal/anonymous nonce composition, owner/Accept interleaving, public resolver registration, anonymous mutable-content invalidation, wrong revision/generation/key/tags, actual body lifetime, native LRU and pending finalization tests remain. Held waiters, VCL-held-reference accounting, pinned read cuts and fabricated drain timeouts are removed with the protocol. |

`test_retired_hold_contracts.py` verifies that removed control operations are
rejected without application execution or authority changes. It does not emulate
their former implementation. Identity observation rejects retired census domains.

## Receipt ownership and real writes

The mock producer must register a real tag event before returning a DIRTY receipt.
A signed receipt cannot create a writer. Request/challenge replay and foreign
receipts remain rejected while the application response and its own cookies remain
intact. Unknown/missing receipts and upstream EOF do not invent a global hold or
clear a real pending tag event.

ACK may collect a completed event while its backend response is still in flight.
The late receipt cannot resurrect that collected event. The active receipt-owner
tests cover valid retained receipts, GC during overlapping requests and stale
receipt rejection, without asserting that GC waits for whole-PHP completion.

## Validation scope

Run changed actors against the matching-source native module with
`SCP_EXPERIMENTAL_REUSE_TEST=1` and `SCP_TEST_COOKIE_MODULE` set. Their `proxy()`
creates its own temporary origin and Varnish daemon; it never reloads the installed
service. Targeted batches are sufficient for this tests-only change; a complete
matrix, real WordPress/SQL, browser, nonce-renewal or LiteSpeed Enterprise acceptance
claim is outside this test fixture's evidence.

The package build excludes `tests/`. The existing 0.13.21 product ZIP must remain
byte-identical; this cleanup requires no version bump or replacement product ZIP.

The shared-native Webuzo cleanup was qualified with 57 distinct targeted tests.
Hestia keeps its actual profile fixture credential (`A` x32), including signed
context keys and authenticated PURGE; it does not copy Webuzo's credential.
Adapter-specific validation and package checks are recorded below separately.

Hestia adapter validation on 2026-11-25: five targeted native HTTP tests passed,
zero skips, using generated Hestia VCL and the matching existing Varnish9.1 DSO.
They cover normal signed dynamic GET/POST and Basic/old-producer preservation,
rejection of retired controls without origin execution/authority change, mixed
personal cart/anonymous nonce zero-origin composition, and actual native body
MISS/refill/reuse. The signed application producer is explicitly mocked; this
is not WordPress, browser, or LiteSpeed Enterprise acceptance. All116 Python
test files parse and direct test imports resolve. No installed service or live
site was changed. The134-file891947-byte product ZIP remains unchanged, SHA256
`f741a8b4781c1f3f3df3128460516f0d5193217cc586c688072c4e9e47b094fb`.

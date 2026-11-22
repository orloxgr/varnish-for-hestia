# Publication reselection capability: Hestia candidate

The 0.23.7 source candidate adds one explicit response field to the existing
successful authenticated UltraCache capabilities query:

```
X-UltraCache-VCL-Publication-Reselect-Version: 1
```

The exact publication-conflict transition already exists in 0.23.6. This change
makes it discoverable through the normal connection lifecycle. There is no new
native module behavior, ABI, purge operation, TTL setting or background worker.
Basic, failed or malformed control requests, ordinary application responses and
non-capability control operations do not advertise the field.

The candidate also releases consumed backend-only ESI cookie/opt-in and routing
carriers before delivery metadata allocation. The top request keeps its original
ESI state; real browser cookies and headers remain intact. The Warm support
scratch field is released after its capability hint is emitted. No header or
workspace limit is increased. This addresses a separate returning-cookie
transport failure rather than changing the collector invalidation protocol.

A compatible producer can use verified support on all current endpoints before
avoiding a collector completion invalidation that would also evict other public
representations of the same URL. Producer registration, scope, policy and epoch
must still match. Unfinished collector selections cannot grant durable complete
guest freshness. Normal content purges, policy changes and actual expiry retain
their existing semantics. The native capability alone does not change the
application collector.

## Qualification scope

Actual native Hestia tests exercise capability authentication, Basic behavior,
spoofed fields, unchanged registration, existing conflict proof validation,
exact publication retirement, independent owners and ordinary Warm projections.
Additional native scenarios exercise an unfinished zero-freshness selection
followed by a complete guest, and retirement of one parent while preserving its
same-URL guest and another public-cookie context.

With the backend cleanup, 59 distinct native test methods passed without skips.
The matching Edge/probe request loses the delivery credential and returns 503
on the preceding VCL; the cleanup returns 200/MISS followed by 200/HIT at the
same 64-entry header limit. The unmarked live navigation succeeded: the extra
diagnostic field exposed the boundary, rather than every normal navigation
failing. Actual browser fields and the full fixture session value are retained.

An overlapping old-to-new VCL load/use/discard keeps the same registry epoch,
declarations, policies and exact cached objects on the guest site and a second
Basic site. Guest publication, authenticated reselection, Warm, private issuer,
continuation and Hestia compatibility regressions also pass. The earlier test
iteration with nonempty resolver names correctly selected twice; its fixture
expectation was corrected to match the captured empty-resolver configuration,
without changing the cleanup runtime.

These native transport fixtures are separate from real WordPress collector and
browser qualification. They do not claim that a header by itself fixes an
application collector defect. No shared service or production site is changed
by these tests. The candidate is prepared for review and is not a published
release. The Hestia installer has not been executed against a production server
as part of this qualification.

See the [shared conflict protocol](../shared/PUBLICATION-RESELECT.md).

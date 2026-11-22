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

These native transport fixtures are separate from real WordPress collector and
browser qualification. They do not claim that a header by itself fixes an
application collector defect. No shared service or production site is changed
by these tests. The candidate is prepared for review and is not a published
release.

See the [shared conflict protocol](../shared/PUBLICATION-RESELECT.md).

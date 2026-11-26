# Authenticated public-parent warming

Hestia 0.24.15 shares its native/VCL implementation with Varnish for Webuzo
0.13.24. Use a compatible WordPress UltraCache warmer, starting with
3.13.13-dev.1389, that verifies a public parent without requiring personal
fragment delivery from the same Warm response. Basic is unchanged.

## Behavior

The existing authenticated `parent-v1` request warms the public HTML parent.
On a fresh parent HIT it performs no origin or private composition work. On a
cold request, the existing public-source resolver and source capture validate
the publication and retain it through the native snapshot backend. They do not
perform a personal prepare merely to populate the public parent.

ESI processing is disabled only for this Warm response. The stored parent keeps
its parsed ESI capability; subsequent ordinary visitors receive normal private
fragments and cookie delivery. Plain parents and ESI comments retain their exact
public bytes in the Warm response.

A successfully completed authenticated Warm reports:

```text
X-UltraCache-Warm-Projection: parent-v1
X-UltraCache-Warm-Delivery: public-parent-only
X-UltraCache-Delivery-Outcome: not-executed
X-UltraCache-Private-Cache: NOT-APPLICABLE
```

These are native request-owned observations. They do not assert that personal
fragments were filled or verified. Caller-provided or origin-provided markers
cannot authenticate a Warm request. Existing Cookie policies, actual Accept
context, request identity, source validation, expiry and owner isolation remain
in force. No new endpoint, queue, setting or cookie exception is introduced.

## Installation

Use the normal addon update and installer described in the [README](../README.md).
The installer builds the matching native module and activates the generated
VCL. Do not patch VCL manually or deactivate the addon to update it. Update the
WordPress warmer to the compatible version before testing public-parent Warm.

## Qualification boundary

The Hestia adapter passed 17 distinct native methods on Varnish 9.1 using its
actual direct-Apache VCL renderer and mock HTTP application producers. Both
Basic and UltraCache generated VCL compiled. Coverage includes cold source and
projected-source capture, zero-origin hot Warm, exact parent bytes, authenticated
authority and real request contexts, forged proofs, invalidation, subsequent
independent private owners, normal source fallback and full private cache reuse.
The installed Lab module directory and services were unchanged.

The shared native build identity and library hash matched the independently
qualified Webuzo candidate. An imported test initially used Webuzo site settings
instead of Hestia's existing alias fixture; correcting that fixture made the
authority test pass without a shared runtime change.

Paired WordPress dev.1389 and Webuzo 0.13.24 application acceptance was reported
successful: ten Warm contexts verified exact public parent bodies without
private execution, and independent browser visits received complete HTML HITs
with separate empty carts. This was not a Hestia production deployment.

The reported full Warm time improved from 123.3 to 106.6 seconds, but the
5–15-second performance target remains unmet. These functional checks do not
establish that the complete performance goal is achieved.

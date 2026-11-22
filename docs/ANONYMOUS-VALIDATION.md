# Complete anonymous publication: Hestia qualification

Varnish for Hestia **0.23.6** was qualified with WordPress UltraCache
**3.13.13-dev.1324** on 22 November 2026. The shared native runtime matches
Webuzo source `12eef3e`; Hestia runtime `d19e678` supplies its own active-site
credential map through its real VCL compiler. The shared module was built
against the installed native engine SDK, without replacing the engine.

## Native and installation checks

- Forty checks passed for complete guest envelopes, literal absent request
  headers, independent guest HITs, scoped issuer proofs, authenticated Warm
  projections, malformed claims and existing delivery outcomes.
- Thirty-six existing checks passed for publication conflict reselection,
  registry lifetime, header budget, cookie-only delivery, request ownership,
  Hestia application compatibility and source-only native activation identity.
- Eighty checks passed for representation selection, real C envelope/selection
  parsing, temporary Hestia deployment trees and installer error/progress output.

These are 156 passing methods, with no skipped methods. One earlier invocation
also named a nonexistent representation test module; its loader error was
retained and the actual representation module passed in the clean 80-check run.
No product change was made to accommodate that invocation error.

## Actual WordPress integration

The application used its normal installed release ZIP and existing clear/Warm
pipeline, with the Hestia compiler and native module on isolated listeners.
Observers and fixtures were outside the distributed WordPress plugin.

- Normal Warm populated both guest and stateful parent projections in ORIG,
  WebP and AVIF. Six first anonymous visits, from two independent visitors,
  returned complete HTTP 200/HIT documents with zero WordPress bootstraps,
  backend links or origin-backed ESI links. Actual WordPress nonces verified.
- Two browser visitors received independent HttpOnly cookie values through
  separate HTTP 204 issuer requests that started after HTML delivery. No
  visitor cookie values were stored in public HTML or native object metadata.
- Actual WooCommerce add/change/remove operations retained independent carts
  and HITs. Normal clear/Warm replaced the guest object and warmed the stateful
  parent. Functional query binding and the visitor's actual tracking route
  remained intact.
- The actual YITH wishlist browser test passed ten visits and four mutations
  with independent visitor ownership and initial complete guest HITs.
- A real 20-second WordPress nonce lifetime expired the old nonces, produced
  valid new nonces and returned the following guest HIT without WordPress work.
  Neither the product clock nor the native lifetime calculation was mocked.
- A same-build native manager restart created a new epoch and empty registry.
  Ordinary Warm restored registration automatically; the next six guest visits
  again returned complete zero-origin HITs. No manual registration or Redetect
  was used. The test controller was corrected to wait for HTTP readiness after
  its first probe arrived before the new child was ready.

The native and application processes belonged to the disposable fixture;
production sites and shared services were not reconfigured for qualification.
The Basic profile does not participate in this negotiated extension.

An earlier application run observed a host-wide invalidation whose initiating
actor has not been established. That separate issue remains open; this release
does not claim to identify or suppress genuine application purges. A one-off
first-Warm failure after resuming a cold fixture also remains recorded; a real
previous-release-to-current-release installation followed by its first normal
Warm passed on the producer owner's fixture.

See [the shared protocol](../shared/ANONYMOUS-PUBLICATION.md) and the earlier
[publication conflict qualification](../shared/PUBLICATION-RESELECT.md).

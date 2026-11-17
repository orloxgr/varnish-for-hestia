# Cookie policy validation

Current native policy: 0.19.1. Both Basic and UltraCache use the common cookie
sheet for Shared/Variant/Private choices, including `_fbp`. There is no native
provider-specific cookie issuer or Meta configuration form. Older reports about
native Meta issuance describe the removed 0.17.0 behavior, not this version.

## Current checks

- Legacy enabled `cookie_delivery` state is retired by native inventory and has
  no effect on rendering, including before reconciliation. Other settings,
  per-site tokens and explicit common cookie choices are preserved.
- Real native HTTP checks cover MISS/HIT without identifier generation, original
  provider Cookie forwarding and multiple Set-Cookie fields, renewal/deletion,
  common `_fbp` Variant/Private choices in both presets, and public-only ESI.
- Shared native cases retain consent variation, site isolation, application
  private/no-store decisions, public variants, private ESI and nonce isolation.
- Original provider Set-Cookie fields reach the requesting visitor unchanged.
  These deliveries remain uncacheable and downstream private/no-store for every
  cookie name. A shared object never stores and replays those personal fields.

## Boundaries

A cache policy is not a cookie issuer or a consent decision. Actual applications
and providers create and renew their own identifiers. The table does not claim
that an origin-only cookie can be newly created on a Varnish HIT: that needs the
provider's real browser/application delivery path. Provider-side consent and
WooCommerce/session/nonce protections remain authoritative.

Validation uses owned VM processes and temporary HTTP origins. No production
site configuration or runtime is modified by these tests.

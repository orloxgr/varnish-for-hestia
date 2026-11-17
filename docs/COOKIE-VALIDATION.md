# Cookie policy validation

Current native policy: 0.20.0. Shared HTML applies to request cookie variation
and eligible response-cookie storage in both Basic and UltraCache.

## Native response behavior

The same cookie-sheet resolver decides every real Set-Cookie name. When all are
Shared, otherwise public HTML is stored without those personal fields. A native
client-task handoff returns the original fields only to the requesting visitor.
Private/no-store, authentication/cart/nonce contracts, mixed unknown/private/
variant response cookies and real Vary remain authoritative. There is no native
provider identifier generator or separate Meta configuration form.

Actual isolated Varnish tests cover concurrent MISS/HIT pairs, exact duplicate
fields, Expires commas, renewal/deletion and attributes, core privacy, explicit
prefix/exact choices, internal-header removal and finalized handoff state.
Shared parity reports include hashes of the native source and build helper.

## Real provider and consent acceptance

Both generated presets were tested with actual WordPress, WooCommerce, Facebook
for WooCommerce, Real Cookie Banner and the published UltraCache dev.1288
provider integration, in a disposable owned fixture. Three fresh browser contexts
received the same warmed public HTML from HIT. Two consenting visitors received
distinct real provider identifiers; the rejecting visitor received none. Returning
visitors preserved their identifier without another issuance call. CMP revocation
deleted the cookie and prevented reissue. Public stored HTML contained no personal
identifiers. Fixture processes, paths and database were removed afterwards.

This application test uses the existing private provider endpoint only when a
cookie is missing and consent permits issuance, not a full-page PHP render on
HIT. Basic response storage itself requires no WordPress plugin. Other providers
continue to use their own browser/application issuance path; a cookie catalogue
cannot invent an origin-only provider’s identifier on a HIT.

## Database lifecycle

Recognition, assessments and executable defaults ship together with plugin
updates. There is no daily metadata-only download. Saved central/site choices
retain precedence; old downloaded snapshots are not deleted during an upgrade.

Validation changes only owned VM fixtures. Production reads used for diagnosis
do not install, purge, reconfigure or restart anything.

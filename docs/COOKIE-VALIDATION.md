# Cookie policy and delivery validation

Release: 0.17.0. Catalogue: 2026.11.16.4.

The catalogue contains 46 reviewed policies. The separately licensed Open Cookie
Database snapshot contains 2,288 recognition records pinned to revision
`7786335566460016f07a50705a92fc781c976f6f`. Recognition categories do not authorize
cache sharing or minting identifiers. No external database is queried per request.

## Native and provider evidence

| Behavior | Evidence and result |
| --- | --- |
| Common Hestia/Webuzo behavior | 89 identical native HTTP runs, with identical policy, catalogue, compiler, delivery module and case bytes. Both Basic and UltraCache are exercised. |
| Independent Meta delivery | Two new visitors receive different identifiers and the same cached public body; an existing identifier remains unchanged. Actual Meta ParamBuilder accepts both native-generated values and adds its own provider appendix when required. |
| Cookie attributes and other fields | Native HTTP checks preserve original multiple Set-Cookie fields, HttpOnly, domain/path, expiry commas, renewal and deletion. Provider cookies take precedence over native issuance. |
| Consent and authority | Native exact-cookie consent follows the current request; actual Meta hold prevents issuance while HTML remains HIT. An application-owned provider endpoint remains authoritative in either preset. |
| Actual Hestia application integration | Real WordPress 7.1.4, WooCommerce 11.2.1, Meta for WooCommerce and Real Cookie Banner Pro 5.4.3, through generated Hestia VCL. Explicit warm-up, three independent browser contexts, actual consent UI, provider endpoint, return and revoke passed. |
| Private fragments and variant keys | An approved common ESI parent with Vary: Cookie serves separate session-bound nonce fragments with MISS/HIT/HIT for A/B/A. Private cart carrier IDs are absent from its public variant dimension. Other functional Vary inputs remain. |
| Downstream privacy | New native cookies, original provider cookies and assembled private ESI deliveries receive response-only private/no-store. Their stored public templates remain reusable. Public-only ESI retains public response caching. |
| Diagnostics | Actual cookie names and decisions only. Malformed Cookie text is not reflected. Forged browser headers cannot enable issuance or approve public HTML. |

The actual Hestia provider fixture used the verified UltraCache dev.1288 package,
with its exact 424 runtime files. Native standalone tests also exercise Basic
without UltraCache or WordPress. The current proxy HIT is verified with X-Cache;
origin cache/source headers in an outer HIT describe its fill response, rather
than a new execution of PHP.

The common application's real two-cart/cross-session nonce, Apache Static,
Basic fallback, warm stored-object and image-variant scenarios were independently
executed in the Webuzo lab. The Hestia-specific proof consists of native parity,
nonce composition and the actual WordPress/provider/CMP fixture above. The
application's direct PHP, early drop-in, actual WP Consent API provider override,
RCB UI, delayed-script and message-export paths were verified by the UltraCache
owner. These are representative verified paths, not a claim about every CMP or
every possible hosting environment.

## Activation and boundaries

Independent native `_fbp` delivery starts disabled and is configured per site.
Use a real Meta integration and an exact consent predicate appropriate to that
site. Complex service/revision or per-plugin PHP decisions retain the actual
provider/CMP endpoint. Consent categories from a lookup database cannot replace
those APIs. Other providers keep their own issuance; no arbitrary sessions,
click IDs, signatures or authentication tokens are generated.

A cold Basic response with original Set-Cookie remains private and reaches its
visitor unchanged. This feature does not add a hidden warmer. Once a public
object exists, eligible visitors can receive HIT plus their own cookie. Unknown
cookies retain existing policy and do not gain an automatic bypass.

All application/service mutations and test identities were confined to owned
lab fixtures. Fixtures, databases, tunnels and temporary processes were cleaned;
shared service PIDs were unchanged. No live site was changed.

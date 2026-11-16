# Cookie policy inventory

This inventory records the starting behavior for the shared cookie-delivery
work. It distinguishes present behavior from the implementation being added.

| Area | Existing mechanism | Responsibility in this work |
| --- | --- | --- |
| Request cookies | `scp_common_recv` applies authentication, session and cart privacy. Other cookies do not by themselves bypass Basic. Original functional cookies reach the origin. | Keep those semantics and generate the named built-in groups from one versioned catalogue. |
| Public variants | `scp_cookie_variation` omits known analytics IDs from the internal `Vary: Cookie` remainder. Functional, unknown, consent, referral and language values remain distinct. Accept and language negotiation have separate internal keys. | Keep public dimensions separate from identity cookies; preserve original downstream Vary. |
| Response cookies | `scp_response_privacy` treats Set-Cookie responses as uncacheable. It preserves the origin fields and lets a later cookie-free response refill normally. | Deliver supported independent cookies outside cached objects without dropping other fields, renewals or deletions. |
| Private cookie rules | The shared VCL contains built-in authentication/session/cart groups. `src/cookie_policy.py` validates explicit per-site bypass names/prefixes. | Preserve administrator additions; replace the duplicate built-in group definitions with catalogue consumers. |
| WooCommerce | Basic passes cart/session requests. UltraCache adds opt-in shared-parent approval and a private ESI carrier for the selected Woo cookies. | Preserve actual cart isolation and session-bound nonce behavior; do not replace it with a second transport. |
| ESI | Native Varnish composes origin-declared HTML includes in the UltraCache preset, including uncached parents. Attribute parsing is enabled natively. | Retain existing same-site scope and private-child rules. |
| Application refill | UltraCache has response-cookie admission, local page storage and an outer-cache clean refill/handoff. The Varnish adapter itself does not implement application refill jobs. | Integrate the existing producer contract instead of introducing hidden scans, warmers or a parallel application cache. |
| Consent | The current Basic policy has no provider/CMP issuer. Existing consent cookies remain functional Vary inputs. | Add explicit provider/consent policy selection and evaluate current consent at delivery; do not infer consent from marketing categorization. |
| PHP / Apache Static / direct origin | These are application delivery paths. The proxy cannot assume PHP runs on a HIT. | The application owner supplies its existing browser/private-endpoint path when the proxy contract is absent. |
| Diagnostics | X-Cache and X-Hestia-Varnish report HIT/MISS/PASS, with a concrete X-Hestia-Varnish-Reason. The panel already exposes site settings and scoped controls. | Add cookie names and policy/delivery decisions, never cookie values or credentials. |

## Overlaps to remove

The application and shared VCL currently maintain separate tracking and private
cookie groups. They also have different response-cookie responsibilities: the
application can store a verified public body locally and arrange a clean handoff,
whereas the proxy sees the complete origin response. A shared catalogue must not
turn either decision into a blanket instruction to discard Set-Cookie.

The earlier native `_fbp` experiment demonstrated request-local generation and
delivery with a reusable body. It did not implement provider normalization,
consent, domains or preservation of duplicated response headers, and is not a
supported production driver. In particular the current Meta Parameter Builder
can normalize a four-part cookie by adding a provider appendix. Origin renewal
must take precedence over any pending edge issuance.

## Native response-header primitive

The official `header` VMOD provides append/get/remove operations for duplicated
headers. It avoids combining Set-Cookie fields, whose Expires attributes contain
commas. The matching `varnish-modules` package is available from the official
Varnish repository for the native 9.1 ABI. Installation and native compilation
must use that existing package mechanism, not a custom replacement cookie VMOD.

## Sources and ownership

The canonical application catalogue is owned by UltraCache under
`resources/cookie-policies/`; panel distributions carry the same versioned data
locally. Hestia leads the shared VCL/compiler, Webuzo maintains its adapter and
independent native parity, and UltraCache maintains application/CMP/provider
integration and WordPress/WooCommerce proofs. Runtime requests do not fetch an
external cookie database. Recognition metadata is separate from executable
policy and retains the source attribution and applicable license.

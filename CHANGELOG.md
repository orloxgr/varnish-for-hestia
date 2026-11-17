# Changelog

## 0.20.0 · 2026-11-17

- Emit identical response-cookie execution rules once across sites even when their editorial row IDs differ. Preserve scoped request diagnostics and verify 48 native hosts with Shared/Variant response-cookie behavior and no replay.
- Put the native build identity in the actual VMOD module directive so C-only updates load a new implementation. Verify native hot reload while an old client task remains active, plus rollback and failed-build retention.
- Apply the common Shared HTML choice to real response cookies as well as request variation. Detach complete original Set-Cookie fields into client-task-owned native memory before storing otherwise public HTML; deliver them only to their original visitor, never through a shared object. Keep duplicate fields, attributes, renewal/deletion and original application/consent ownership.
- Clean discarded cookies on backend retry/error, client restart and abort. Compile the small shared helper for the installed native ABI without upgrading/restarting the engine; rebuild before native startup after APT ABI changes. Native-source-only changes activate a new VCL generation.
- Ship recognition descriptions and reviewed executable defaults together with plugin updates; remove daily metadata-only downloads and their controls. Preserve saved central/site choices and old snapshots for rollback. Retire the stale native Meta-issuer capability declaration.
- Verify concurrent native delivery, private/unknown/variant boundaries and actual Meta/WooCommerce/RCB browser consent lifecycle against both generated presets.

## 0.19.1 · 2026-11-17

- Remove native Meta `_fbp` issuance, its per-site form/action and provider-specific VCL compiler. Retire old issuer settings during inventory. All cookie cache choices use the common sheet; applications/providers own identifier creation and actual consent. Preserve original provider fields, generic downstream privacy and private/public ESI behavior.

## 0.19.0 · 2026-11-17

- Reuse identical cookie execution projections within each reconciliation stage instead of expanding the full defaults twice per hosted site. Avoid projection work for disconnected WordPress integrations while retaining signed disconnect operations, scoped change detection and cache invalidation.
- Give every bundled cookie a concrete, editable Shared/Variant/Private default. Compile these decisions into both presets and materialize the same versioned snapshot for connected WordPress consumers. Keep site > admin > bundled priority, core privacy, original cookies, consent and the approved WooCommerce/ESI contract.
- Replace the cramped cookie sheet with hidden internal IDs, equal-height controls and a clear Why / precedence button that expands a full-width explanation of actual behavior, evidence and priority. Offer only concrete actions; resolve legacy Automatic snapshots reproducibly without discarding saved choices.
- Escape legacy literal cookie names, use UTF-8 byte ordering across consumers, index prefix resolution, compile the bundle into guarded action groups once even for distinct site overrides. Preserve empty disconnect/rollback snapshots and synchronize/invalidate transactionally when executable bundled rules change; editorial-only updates do not invalidate caches.

- Preserve genuine origin Cookie variation when an unconnected response carries empty policy headers. Require an actual scoped digest before trusting the policy-only marker; report the real selected/functional/private-fragment/consent cause without cookie values.

## 0.18.2 · 2026-11-17

- Add the scoped cookie-policy spreadsheet, separate recognition/assessment proposals, native site overrides and optional signed UltraCache WordPress integration. Publish the common policy from six explicit source modules as a complete immutable runtime VCL.
- Fix upgrades of large multi-site configurations: native `vcl.show` can return `201` with truncated source. Runtime identity now uses the complete program's managed digest name; boot/external reload programs are adopted once through native compilation and activation, without dumping source, changing CLI output limits or restarting Varnish. Repeated reconciliation reuses the active managed generation.
- Reproduce the failure on actual native Varnish, then verify large-policy upgrades, independent runtime/disk restoration, one-time boot adoption, module-only changes, failed-candidate retention and recovery regressions.

## 0.18.1 · 2026-11-16

- Check upstream CSV column count before the CSV parser allocates field arrays. This prevents memory amplification from many tiny columns inside an otherwise size-bounded download. Preserve quoted commas, escaped quotes, multiline fields and legitimate Unicode; the current upstream database has ten columns.
- Add targeted pre-allocation rejection and valid quoted-field/128-column tests. Executable cookie policy, VCL, consent and provider behavior are unchanged.

## 0.18.0 · 2026-11-16

- Update cookie recognition metadata directly from the original Open Cookie Database GitHub repository, independently of plugin-code releases. Daily updates default on; administrators can disable them, check status or use Update now. Preferences and the downloaded snapshot survive code updates.
- Use one shared updater for both panel distributions, with verified HTTPS, fixed revision-pinned URLs, no redirects, bounded untrusted input, strict CSV/UTF-8 validation and an atomic root-private last-good record. Preserve legitimate Unicode and the upstream's optional empty provider field.
- Keep downloads separate from the Varnish operation lock and visitor requests. Recognition updates do not change executable cookie policies, consent, VCL, website overrides or cache contents. Show stage-specific failures and retain the last valid database.
- Verify 47 targeted Linux checks and actual native Hestia admin Update now, persisted settings, role/CSRF rejection and escaped UI text, with no VCL changes or service restart. Actual upstream download contains 2,288 records; the next check detects no change.

## 0.16.4 · 2026-11-16

- Reduce Basic cache fragmentation without an application plugin: simple `Accept` and `Accept-Language` lists reuse variants across token case and equivalent quality notation, including default quality 1 and fractional trailing zeros. Original origin headers and downstream public Vary remain intact; the same base behavior applies to UltraCache.
- Preserve actual languages, media types, preference order, different qualities, case-sensitive media parameter values, quoted values and nonstandard syntax. Requests are not blocked or rewritten, and private/session policy is unchanged.
- Add six shared native HTTP fixtures covering reproduced Basic misses, equivalent reuse, real negotiation differences, combined Cookie/Accept/language variation, forged internal keys, quoted parameters and absent/empty headers. Keep the shared policy and fixtures identical in both panel distributions.

## 0.16.3 · 2026-11-16

- Enable native ESI parsing inside HTML attributes via `esi_ignore_other_elements`. Persist the startup flag in the managed service unit and enable it additively on upgrade through the authenticated native CLI, with no Varnish restart or automatic cache flush.
- Preserve other runtime feature flags, startup cache size and private-parent admission. Restore the prior managed unit if native feature activation fails. Keep the shared VCL byte-identical to Webuzo 0.4.4; no response-cookie replay or login-cookie expansion.
- Add native tests for inline JavaScript, JSON and attribute composition; repeated private nonce fetches across visitors without cached nonce/cookie leakage; runtime activation; managed-unit rollback; and uncached cold parents composing mini-cart ESI while retaining their native nonce and response cookie.

## 0.16.2 · 2026-11-16

- Port the shared Webuzo stored-HTML Accept fix unchanged. Accept an actual origin `X-Ultra-Cache: HIT` alongside Apache-static provenance, so warmed PHP page-cache objects and stored ESI parents can serve the first compatible browser Accept without another origin fetch.
- Keep the public/cacheable/status/HTML/variant/no-Set-Cookie conditions, original origin Accept, real codec negotiation and ESI privacy rules. New dynamic `STORE` responses retain raw Accept variation.
- Add the same shared native HTTP cases for PHP cache HIT reuse, warmed ESI parents with separate personal fragments, dynamic STORE variation and Set-Cookie privacy. Keep the shared runner unchanged and the Hestia adapter native.

## 0.16.1 · 2026-11-15

- Show timestamped installer stages, actual work counts where available and a current-stage heartbeat during slow work or lock waits. Reporting adds no work deadline and stays silent outside the administrator installer.
- Replace the default final JSON dump with a readable success/failure summary, installed version, full result details and elapsed time. Retain explicit `--json` mode with progress/diagnostics on stderr and one JSON document on stdout; preserve native failure details and nonzero exit status.
- Keep panel, background and internal JSON interfaces unchanged. Respect `NO_COLOR` and plain redirected logs; a closed reporting stream cannot cancel completed installation work.

## 0.16.0 · 2026-11-15

- Ship one unchanged `shared/cache-policy.vcl` with Webuzo, covering Basic/UltraCache request, privacy, session, ESI, representation and lookup-key rules. Remove the duplicate Hestia common/UltraCache policy sources and built-in Python cookie lists. Keep Hestia host/backend/token boundaries, transport, custom additions and panel headers in the adapter.
- Normalize a copy of the URL for cache lookup and authenticated exact/soft invalidation. Different known campaign IDs reuse a public page; preserve the full original URL and analytics cookies at the origin. Keep functional queries, referral, language, currency and functional Cookie variants distinct. Regex/batch BAN selects canonical lookup URLs.
- Share origin-attested static HTML Accept capability grouping, equivalent unquoted Accept whitespace normalization, original origin Accept, real JSON/XML/image negotiation and q=0. Keep Cookie's functional remainder for both static and dynamic representations. No addon Accept length/item optimization cutoff.
- Cover WordPress/WooCommerce private routes in subdirectories. Reset ESI request flags independently for each subrequest while retaining the top-level private-cookie carrier, so public ESI fragments remain reusable and personal fragments remain separate.
- Publish the complete shared directory atomically with the addon. Keep distributions independent and use identical native HTTP parity fixtures to verify the generated panel adapters; no cross-repository runtime or installer check.

## 0.15.1 · 2026-11-15

- Use the running Varnish's `param.uncacheable_ttl` for hit-for-miss markers instead of an addon-owned 120-second lifetime. Remove forced marker grace/keep values and UltraCache's five-minute keep override; preserve native, origin and explicitly configured retention.
- Preserve the origin's Cache-Control on ordinary Set-Cookie responses while keeping those responses uncacheable in Varnish. Retain explicit downstream privacy for private ESI fragments, unapproved session parents and consumed private/no-store Surrogate-Control.
- Remove the blanket HTTP status >=400 caching exclusion. Public errors follow their origin/native freshness; private/no-store/expired responses remain uncacheable.
- Install the signed APT candidate instead of pinning one Varnish package build or manually removing a particular library generation. Let APT resolve dependencies. Retain Ubuntu/amd64, the matching resolute repository, signing-key verification and checks against removing unrelated services. Addon updates still preserve the installed native package.
- Verify native runtime retention settings, long origin freshness, public error HITs, separate Set-Cookie deliveries and installer package selection without changing production.

## 0.15.0 · 2026-11-15

- Replace four preset choices with Basic and UltraCache. Both use one HTTP/WordPress/WooCommerce policy; UltraCache adds only its ESI/private-fragment/approved async-parent integration.
- Make public search, REST and XMLHttpRequest GETs and referral URLs eligible for caching. Preserve authentication/nonces, login/account/checkout/cart mutations, Store API cart/checkout and real session isolation. Keep original query parameters and referral attribution at the origin and in distinct cache keys.
- Collapse equivalent unquoted Accept whitespace without changing media types, quality weights or q=0. Honor origin representation variants. Normalize only known analytics IDs out of the internal Vary: Cookie key; retain functional/unknown cookies, complete origin cookies and downstream Vary: Cookie.
- Unify HIT/MISS/PASS across X-Hestia-Varnish and X-Cache and add a concrete X-Hestia-Varnish-Reason. Keep mandatory private/no-store/Set-Cookie decisions and hit-for-miss behavior. Preserve downstream privacy headers after ESI consumes Surrogate-Control and for unapproved private parents.
- Convert existing General/WordPress/WooCommerce site/default selections to Basic during reconciliation, preserving tokens, IDs and settings. Fold old central additions into their sites before local additions; keep UltraCache rules. No former runtime preset implementations remain.
- Use a new cache namespace for the changed policy. Add native Varnish coverage for public reads, referral handoff, warmup/browser reuse, cookie/Accept variants and two independent Woo sessions. Production is not modified by tests.

## 0.14.1 · 2026-11-12

- Show immediate timestamped installer progress: operation-lock wait/acquisition, account inventory, code publication, managed routes, native VCL compilation/activation, each changed domain, web configuration validation/reload and final commit.
- Report the current stage every ten seconds while a native operation is still running. This is visibility only; no new timeout, cancellation or work limit is introduced.
- Keep progress on stderr and final JSON on stdout. Panel/API and cron operations remain silent unless explicitly run in an administrator reporting context. A closed progress console never converts successful work into failure.
- Preserve the 0.14.0 VCL, cookies/query policy, credentials, cache budget and warm objects; add regression coverage for reporting, domain counts and output separation.

## 0.14.0 · 2026-11-12

- Let explicitly opted-in UltraCache cart/session visitors HIT a warmed public parent marked `X-UltraCache-Woo-Async-Parent: 1`. Keep private cart endpoints, login exclusions, response privacy, Vary isolation and the ESI-only private cold-miss approval unchanged.
- Derive Varnish connect/first-byte/between-byte allowances from the loaded native Nginx hosting configuration and give the outer proxy time to complete those phases. Preserve saved administrator first-byte overrides. Apply live without restarting Varnish; Apache and PHP retain their native limits.
- Preserve parent response-header inheritance, including HSTS, when adding static browser headers using native Nginx 1.29.3+ header merging.
- Add central and per-domain browser cache controls for existing Nginx static-file routes: ordinary lifetime, declared content-hashed immutable paths, revalidation with zero lifetime, and inheritance. Default ordinary assets to 30 days and declared versioned assets to one year. Add the UltraCache CSS-bundle preset by profile, retaining custom paths.
- Add centrally editable request/response additions per profile and a default profile for newly discovered domains. Retain existing site profiles and local additions; invalidate only sites whose effective profile rules change.
- Report uncacheable deliveries as BYPASS instead of MISS. Public misses and cache hits keep their normal meanings.
- Retain generic public HTML/CSS/HTTP caching, functional query keys, unknown-cookie handling, origin TTLs, tenant tokens, cache size and native security boundaries. No new request-size, output, rule-count or execution-time quotas.
- Add native Varnish and Nginx regression coverage for async cart isolation, query variants, non-HTML objects, timeout inheritance, static response headers and scoped policy changes.

## 0.13.1 · 2026-11-05

- Fix HTTP 503 "VCL failed" during authenticated contract exact/batch BAN of long URL expressions. Parse quoted operands in non-capturing, possessive chunks instead of retaining regex backtracking state per character, preserving the accepted grammar without changing native server limits.
- Keep token authentication, site/host isolation, operation checks and malformed-expression rejection. Add native regression coverage for 2,400/3,400-byte queries, long escape-heavy batches, malformed operands and unaffected cached objects.
- Existing installations apply the corrected generated VCL through the normal pull-and-installer update, retaining site settings, credentials and memory budget.

## 0.13.0 · 2026-11-04

- Remove addon request/file/output ceilings, subprocess/download deadlines and the Referer interstitial; preserve authentication, CSRF, tenant scopes, native compilation and rollback.
- Remove forced 1-second upstream connect, failure-count/failure-window and two-try overrides from generated proxy templates. Existing server-selected first-byte timeout and cache budget are retained.
- Accept positive cache sizes and nonnegative native timeout values (including fractional seconds) and complete cookie/VCL rule lists without arbitrary addon size/count/nesting quotas. Cookie rules remain literal names/trailing-star prefixes; generated regular expressions escape literal characters safely.
- Remove the 3,000-character BAN expression restriction while retaining authenticated, anchored site/host scoping.
- Support authenticated exact soft purge using the native purge VMOD, preserving grace/keep and unrelated URLs/hosts. Advertise soft-purge in the VCL contract.
- Use the authenticated native CLI protocol without a separate client work deadline. Health checks distinguish actual stopped/failed services from startup still in progress.
- Allow native loopback ports at initial installation/adoption and validate restore/configuration against the installed native service instead of exact release pins. Signed/checksummed fresh-install packages are unchanged.

## 0.12.0

- Apply the common cookie policy to General: tracking and unknown request cookies
  no longer bypass public HTML, CSS or other cacheable HTTP content by themselves.
- Retain known login/session/cart exclusions, per-domain cookie rules, original
  cookies on origin misses, and response privacy/Set-Cookie protections.
- Refresh only General's cache namespace when upgrading from 0.11.0. Keep the
  warm caches of WordPress/WooCommerce/UltraCache and the existing static routing.
- Update panel help and verify generic HTML/CSS, private sessions, response-cookie
  handoff and live upgrades with native Varnish.

## 0.11.0

- Use application cookie exclusions in WordPress/WooCommerce/UltraCache instead
  of bypassing every unrecognized cookie. Preserve cookies on origin misses.
- Bypass known WordPress private state, PHP sessions, cart state and common Woo
  personalization cookies. Retain explicit UltraCache shared-parent approval
  and isolated private ESI cookie transport.
- Add per-domain exact cookie names and trailing-star prefixes in the Hestia
  owner panel, also available to administrators managing that website.
- Store rules through the existing scoped configuration transaction, migration
  and backup paths. Changes invalidate only that site's cache and aliases.
- Handle multiple Cookie headers before applying exclusions. Keep General's
  application-independent bypass policy and all response privacy protections.
- Start a fresh cache namespace on upgrade; keep profile, tokens, VCL and memory.

## 0.10.0

- Keep a two-minute hit-for-miss decision for uncacheable responses, allowing
  concurrent origin fetches without storing private response bodies.
- Respect `Surrogate-Control: no-store` in all profiles, including responses
  whose ESI processing consumes that header.
- Strip only known analytics cookies on public WordPress/WooCommerce requests;
  retain login, cart, language, currency and unrecognized cookies as cache bypasses.
- Start a fresh cache namespace for all profiles so pre-update objects cannot
  bypass the corrected privacy policy. Tokens, settings and routing are retained.
- Verify privacy, ESI, purge variants, cookie boundaries, live VCL upgrades and
  concurrent uncacheable fetches with native Varnish.

## 0.9.0

- Add administrator cache size editing in Hestia, shared across all websites.
- Apply through the existing native service with an explicit restart button,
  runtime storage verification and durable rollback after failures/interruption.
- Retain the saved budget through updates and configuration backup/restore.
- Explain units, shared scope and restart behavior in mouse-over help.

## 0.8.0

- Add an administrator server-wide backend first-byte timeout in the Hestia
  overview, applied live to all Varnish origins, including cache-bypass requests.
- Keep the native service default until explicitly configured. Persist the
  setting through existing desired/applied state, configuration journals,
  account discovery and backup/restore, without editing service-unit defaults.
- Add an on-demand native `varnishstat` memory snapshot. No background collector,
  request-log analysis, automatic polling or policy synchronization on this action.
- Add mouse-over explanations to administrator and site-owner controls.

## 0.7.0

- Fix HTTP BAN clearing a whole site when only selected URLs were requested.
- Support exact and batch URL bans, HTML-only invalidation and explicit host invalidation, with immutable site and host boundaries.
- Add authenticated UltraCache HTTP contract v2 with the `ultracache-hestia-v2` adapter and accurate control capabilities.
- Reject malformed or unauthorized invalidation requests without clearing unrelated objects.
- Preserve existing UltraCache cache keys; start a fresh namespace for older profiles missing URL metadata.
- Verify generated product VCL with native Varnish, including unrelated objects, aliases, tenants, Vary variants and private ESI visitors.

## 0.6.2

- Fix dropdown links closing before pointer clicks can navigate.
- Preserve internal keyboard focus and navigation when another installed addon still has an older menu script.

## 0.6.1

- Keep the original Accept header in the UltraCache profile for ordinary PHP APIs and content negotiation.
- Bypass standard cart, checkout and account paths in UltraCache without relying on an application plugin.
- Verify all profiles against plain HTTP origins, sessions, private responses and optional ESI.

## 0.6.0

- Add an administrator dashboard listing all native accounts and websites.
- Add bulk account/site enable and disable, plus direct owner management.
- Apply a profile to selected or all websites while retaining site VCL and tokens.

## 0.5.4

- Render addon pages with Hestia’s native header, navigation, selected theme, forms and alerts.
- Keep owner actions in HTML and show visible success or failure feedback.
- Remove the legacy website-access probe from the owner interface.

## 0.5.3

- Add a Plugins menu in Hestia’s top bar through its native custom-scripts loader.
- Share one dropdown with other installed addons, without editing Hestia templates.
- Install, update, roll back and remove only this addon’s menu script.

## 0.5.2

- Create the shared Hestia plugins directory when installing the first addon.
- Preserve existing plugin-directory permissions and neighboring plugins on installation and retry.

## 0.5.1

- Administrator installation failures show command arguments, exit status, subprocess output and Python tracebacks.
- Panel PHP syntax-check failures retain native compiler diagnostics.

## 0.5.0

Initial release.

- Shared native Varnish service with isolated host, backend and purge scopes.
- General, WordPress, WooCommerce and UltraCache profiles, including ESI.
- Bounded site-local VCL editing with native compiler validation.
- Owner token, scoped purge and enable/disable controls.
- Additional Hestia proxy templates and native origin fallback.
- Automatic account/domain lifecycle discovery and package policy.
- Private configuration archives, cold restore and independent removal.
- Durable installation, live-configuration and restore recovery.
- Atomic installed-code generations and failed-upgrade rollback.
- Application configuration remains independently managed.

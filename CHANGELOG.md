# Changelog

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

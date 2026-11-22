# Varnish for Hestia

One shared Varnish service, separate site caches and purge tokens, with per-site
profiles and VCL controls. Version **0.23.4** · GPL-3.0-or-later.

UltraCache prepare requests clear completed routing/selection scratch before
adding their authenticated transport fields, retaining ordinary browser headers
and native Vary inputs at the default 64-entry HTTP header limit. Resource
exhaustion and a real repeated prepare now have distinct diagnostics.
See [backend header budget](shared/BACKEND-HEADER-BUDGET.md).

Cookie choices apply through one scoped resolver. CMS session defaults are visible
and editable, and old website bypass lists migrate into ordinary Private rows.
See [CMS choices](shared/CMS-COOKIE-CHOICES.md).

A compatible UltraCache application and native Varnish now report the completed
request's prepared private fragment outcome separately from parent cache HIT.
The outcome works with Debug off; Debug retains its separate optional value-free
VSL diagnostic. Native Varnish never generates provider cookie identifiers.
See the [delivery outcome contract](shared/DELIVERY-OUTCOME.md).

Registered UltraCache applications now prepare their public representation on
an eligible cold MISS even without resolver-cookie variants. Plain warm HITs
retain zero backend work. See [cold public selection](shared/COLD-PUBLIC-SELECTION.md).

Observed server-cookie publications can negotiate a separate
[cookie-only delivery contract](shared/COOKIE-ONLY-DELIVERY.md). A marked HIT
reuses public HTML and executes its actual application issuer once per visitor,
including its real consent and lifecycle decisions. Original cookie fields stay
request-owned. Unmarked plain pages keep their zero-backend path; Basic keeps
its existing best-effort behavior without ESI. Existing old WordPress publications
need the application's normal capability redetection, cache clear and warm-up
after both compatible components are upgraded. A native addon update does not
rebuild an old local application snapshot. See the [qualification record](shared/COOKIE-WARM-VALIDATION.md).

The UltraCache profile supports request-owned cookie delivery before private
fragment composition, scoped private-fragment TTL, actual application-private
documents, and exact public-fragment TTL/error containment. **Basic stays best
effort without ESI.** Cookie Database remains the sole cookie classification
authority. Profiles provide independent cookie choices and
[application-scoped public selection](shared/PUBLIC-SELECTION.md), including
actual provider context before lookup and private streaming/range delivery.
Common bundle `2026.11.21.1` keeps personal commenter, YITH, Recently Viewed,
cart/session and User Switching defaults Private in Basic and Shared in the integrated UC profile;
manual choices still win. The [current qualification record](shared/COOKIE-WARM-VALIDATION.md)
separates native, application and installation checks; [earlier evidence](shared/ESI-VALIDATION.md)
remains the historical record for 0.22.0/0.11.0.

## Quick start

Requires **Ubuntu 26.04 amd64 with Hestia 1.10.x already installed**, using
**Nginx -> Apache/PHP-FPM** (Nginx 1.29.3+ for native response-header inheritance). Run commands over SSH as an administrator. The
installer also installs the signed Varnish package selected by APT from the
official repository for this distribution; do not install the service separately.

1. **Get the code. Choose one command:**

   For a **new installation**, clone the repository:

   ```sh
   sudo git clone https://github.com/orloxgr/varnish-for-hestia.git /usr/local/src/varnish-for-hestia
   ```

   To **update an existing checkout**, pull instead:

   ```sh
   sudo git -C /usr/local/src/varnish-for-hestia pull --ff-only
   ```

   Wait for Git to finish successfully before continuing.

2. **Install or apply the update.**

   For a **new installation** with an 8 GiB cache budget:

   ```sh
   sudo python3 /usr/local/src/varnish-for-hestia/tools/install.py --memory-mb 8192
   ```

   For an **update**, retain the existing memory budget:

   ```sh
   sudo python3 /usr/local/src/varnish-for-hestia/tools/install.py
   ```

   Pulling the code alone does not apply the update; run the installer too.

3. **Check that Varnish is running.** The output should be `active`.

   ```sh
   sudo systemctl is-active varnish
   ```

4. **Log into Hestia as the site owner. Click Plugins → Varnish in the top bar.**

   Sites start enabled with **Basic**. Choose **Basic** for WordPress/WooCommerce
   without UltraCache (also best effort for other HTTP sites), or **UltraCache**
   for the same policy with ESI/async integration, then save. Administrators see all accounts
   and websites, with bulk profile and enable/disable controls.

Done. Existing users and sites are added during installation; new ones are picked
up automatically within a minute. Each owner can edit the supported VCL sections,
change purge tokens, clear cache, or disable Varnish for a site or their account.
All profiles work with plain PHP or WordPress, independently of installed plugins.

The **8 GiB budget is shared by all sites**, not allocated per user. This example
is sized for a **32 GB server**: Varnish also uses RAM outside cache storage,
and PHP, databases and other services need their own RAM. Hestia's existing code
and templates are not replaced.

This repository is public; cloning does not require GitHub credentials.

## Server cache and CMS rules

Each website has **Server cache and CMS rules** in its existing accordion.
**Enable aggressive caching** is off by default and works with Basic and
UltraCache. When enabled, anonymous public HTML uses the selected positive
**Server cache duration (seconds)**, including when generic origin cache headers
request private/no-store or a shorter lifetime. The original browser cache headers
are restored on delivery. This option does not change browser cache settings.

Aggressive caching does not change cookie actions. The same bundled defaults and
saved per-profile Shared HTML, Public variant and Private choices apply, including
Private defaults for `PHPSESSID` and `__Secure-PHPSESSID`. CMS-discovered opaque
cookie names are no longer silently Shared; ordinary selected rules and functional
Vary handling apply. Private routes/actions remain separate. Original request URL
and cookies reach the origin unchanged. Only Shared response cookies use the
request-owned handoff; their fields never become part of a replayed object.

CMS detection uses Hestia's native document root, including custom document
roots and nested installations. Known WordPress/WooCommerce, Joomla, Drupal,
Magento and PrestaShop private paths and query actions are added automatically.
Static Magento backend aliases and read-only WordPress/WooCommerce, Joomla and
PrestaShop database route metadata enrich these rules where available. Detection
shows its status and retains last valid configured routes when metadata fails.
Use **Additional private path prefixes** only for custom URL prefixes, one per line.
Use **Excluded CMS directories** in the same website form for retired copies,
for example `/old-site/httpdocs`. Each literal path is relative to that website's
native document root and skips the entire subtree before configuration reads or
database queries. Saving retires its detected routes and cookie names, including
previously retained metadata; files and URL access are unchanged. Other sites and
the active CMS at `/` remain eligible for detection. `/` excludes all detection.

Installation, saving cache behavior and **Refresh CMS detection** read metadata
as the hosting account without running customer PHP. Normal panel reads and
minute reconciliation do not recursively scan sites or query route databases.
A native document-root change triggers one refresh; failed discovery after such
a change pauses that website's cache with `cms-document-root-changed` until
detection succeeds. Root can explicitly refresh all websites with:

```sh
sudo /usr/local/hestia/bin/v-varnish-hestia refresh-cms
```

Aggressive request handling runs entirely in VCL. A warm public HIT requires
no Python worker, session database query, token fetch or origin request. Joomla
cookie names are recognized statically during CMS detection. HTML is cached
unchanged, including any application-generated tokens already inside it; this
mode does not verify opaque session authentication or personalize those tokens.
Known login markers, private routes and explicit cookie choices still apply.
The former CMS session service is removed after the new VCL activates during an
upgrade, with owned-resource recovery retained for a failed apply.

## Cookies on cached pages

**Cookie policies** opens the searchable editor. Administrators have central
choices under **All accounts**; account owners edit only their own websites.
The table shows literal cookie names/prefixes, descriptions and concrete cache
actions. Internal IDs stay hidden. Compact controls and a multiline description keep rows readable; the
Why / precedence button opens the full-width behavior, evidence and priority. You can add rows, paste
tab-separated rows from Excel, select rows for bulk changes, and reset local
choices to the inherited policy. Save validates and compiles the actual VCL.

- **Shared HTML:** omit this value from Cookie variation, preserving the real
  cookie in the browser and origin request.
- **Public variant:** include the selected cookie pairs in lookup even without
  origin `Vary: Cookie`; tell downstream caches about Cookie variation too.
- **Private:** pass the request to the application and deliver it as no-store.

Site choices precede central choices; exact names precede longer-to-shorter
prefixes within each scope. Core login/session/cart and origin privacy still
apply. Every bundled cookie has our prefilled, executable decision. Estimates
are labeled as inferred; categories never select an action. Legacy Automatic
choices resolve to the matching bundled decision, or Public variant when none
exists. A prefix never borrows the decision of its first child. Upstream updates do
not overwrite saved choices. Only executable changes invalidate the affected
website cache; editing a description does not purge pages.

The cookie editor has independent **Basic** and **UltraCache** columns. Each
uses Shared HTML, Public variant or Private, with its own central/site overrides
and Reset. Commenter cookies default to Private in Basic and Shared in UltraCache;
other cookie defaults are identical. Old saved choices remain explicit in both
columns. Only the active profile is projected into the existing WordPress sync.

Basic remains independent of WordPress. The optional per-site **WordPress
integration** targets an explicitly configured compatible UltraCache control
endpoint using the existing site token. A compatible UltraCache installation
applies the same scoped policy in its PHP/drop-in and Apache Static delivery.
The native transaction prepares, commits and recovers the application snapshot
alongside the VCL; an authenticated application failure reports its specific
stage and cause. An owner can inspect or reset the managed WordPress snapshot
with `wp ultracache cookie-policy status --format=json` or
`wp ultracache cookie-policy reset --format=json`. Reset invalidates the configured
native Varnish site and keeps panel choices, which an explicit Save can reapply.
An actually selected unsupported native consumer, currently LiteSpeed with
managed Variant/Private rules, reports that concrete capability limitation.
An inactive engine preference does not block working PHP/Apache consumers.

Matching connected origin policies avoid unnecessary tracking-ID variation.
If the application reports a different effective policy and `Vary: Cookie`,
Varnish retains that complete variation and still caches each representation;
an older Shared choice cannot collapse newer application variants. Connection
does not provide a generic cookie issuer or replace the actual provider integration.

Every cookie, including Meta `_fbp`, uses the same cookie-policy editor.
The proxy does not mint provider-specific identifiers. Applications/providers
create, renew and delete their own cookies under their actual consent rules.
Shared HTML applies to both request variation and response storage. When every
Set-Cookie field has a Shared action, an otherwise public response stores its
HTML without those fields and delivers the original fields only to the visitor
who caused the fetch. Duplicate fields, attributes, renewal and deletion remain
unchanged. A later HIT never replays another visitor’s cookies. Providers use
their existing browser or private application delivery path to issue cookies
on a HIT; this mechanism does not invent identifiers or grant consent. Old per-site `cookie_delivery` settings are retired on reconciliation.

The bundled assessment covers 2,288 source records, with 2,293 editable rows
including the additional reviewed rules. Every row has Shared HTML, Public
variant or Private handling. The evidence distinguishes reviewed rules from
inferences; an inference is not a claim of site-specific verification. Where
the source does not establish identical initial HTML, our concrete decision is
a Public variant, without forcing a bypass. Original cookies, consent, core
privacy and the verified WooCommerce/ESI contract remain authoritative.

Recognition descriptions and executable defaults ship together in a reviewed
plugin version. Central/site choices survive updates and retain precedence.
There is no separate daily download of descriptions without corresponding rules.
Maintainers rebuild the pinned source:
`python3 tools/build-cookie-assessments.py --source open-cookie-database.csv --revision <full-upstream-commit> --output shared/cookie-assessments.json`.
This writes both assessments and the exact generated `cookie-defaults.json`
snapshot. It records source SHA-256, revision, reasons and confidence. It never
contacts installed websites. A connected WordPress installation receives that
same flattened default/admin snapshot plus its site overrides through the
existing signed prepare/commit protocol. Its committed snapshot remains frozen
until the next successful synchronization. Disconnect sends an empty signed
clear and returns the application runtime to its standalone bundled defaults.
The signed empty snapshot identity remains separate from its actual runtime
digest, so recovery can restore the previous managed ownership and choices.

### Cookie database updates

**All accounts → Cookie database · reviewed rules** shows the bundled source
revision, record count, executable rule count and rules version. Updating this
plugin installs the reviewed descriptions and functional choices together.
Existing downloaded-only snapshots are preserved for rollback but no longer
supply extra undecided rows. Central and website choices remain authoritative.
The old `update-cookie-database` command reports this lifecycle without fetching
or claiming that a download updated cache behavior.

The request-owned native cookie-handoff extension is built locally using `varnish-dev` matching
the installed engine. Installation does not upgrade or restart Varnish. The
package dependency keeps those headers aligned during future APT upgrades;
a systemd pre-start step rebuilds the extension if the engine ABI changed. Running
visitor requests never read a database or contact GitHub.

Inspect `X-Cache-Cookie-Names`, `X-Cache-Cookie-Role`,
`X-Cache-Cookie-Policy` beside `X-Cache` to see the
applied policy. These diagnostics contain names and decisions, never cookie
values. See [the common contract](shared/CONTRACT.md) for the wire protocol.

## Update

Run these commands separately. First, download the latest code:

```sh
sudo git -C /usr/local/src/varnish-for-hestia pull --ff-only
```

After Git finishes successfully, apply the update:

```sh
sudo python3 /usr/local/src/varnish-for-hestia/tools/install.py
```

Updates retain existing tokens, site settings and memory budget.
Version 0.21.0 keeps aggressive request handling entirely in VCL and retires the
former CMS session service after successful activation. It uses a fresh cache
namespace so old Joomla token templates cannot be reused; pages refill on demand.
Aggressive caching remains off unless explicitly enabled for that website.
The installer prints timestamped stages and actual account/domain counts to
stderr as it works. During a slow native command or lock wait it reports the
current stage every ten seconds; this does not set an execution deadline.
The default final output is a readable summary with the installed version, actual
result details and elapsed time. Add `--json` for a single machine-readable JSON
result on stdout; progress remains on stderr. Panel/API and cron interfaces keep
their existing JSON contract and do not emit installer progress. To keep both progress and the result in a local terminal log:

```sh
set -o pipefail
sudo python3 /usr/local/src/varnish-for-hestia/tools/install.py 2>&1 | tee varnish-install.log
```

Version **0.16.0** ships the same shared Basic/UltraCache policy source as Webuzo.
Existing General, WordPress and WooCommerce selections become Basic automatically.
Site IDs, tokens, enable settings, cookie rules, browser settings and local VCL
are retained. Former central profile rules are prepended to the corresponding
sites' local VCL, retaining their original scope and execution order. UltraCache
selections and their central rules remain UltraCache. The conversion is idempotent.

The installer regenerates the VCL and managed domain routes. Version 0.16.0 uses
a new cache namespace for the normalized lookup URL and shared representation
policy; pages refill on demand. No Varnish restart or manual domain rebuild is
needed. Refresh Hestia with **Ctrl+F5**.

## Cache behavior

**Basic** supplies public HTTP caching and the common WordPress/WooCommerce
private-state handling. **UltraCache** adds ESI composition and explicitly approved
shared parents using exactly that same base policy. No application detection or
extra protection switches are required.

There is no addon TTL cap or forced grace/keep duration. With aggressive caching
off, freshness follows the origin and native Varnish, with explicit central/site
VCL additions retained. Aggressive mode uses the selected website server TTL.
Uncacheable-response markers use the running Varnish's `uncacheable_ttl` setting.
Otherwise public responses whose Set-Cookie names are all Shared can cache
without storing personal cookie fields. Mixed Private/Variant/unknown response
cookies retain uncached delivery. Origin private/no-store is never rewritten
to public. Personal ESI/session responses retain their privacy
headers. The native freshness of errors is retained; a positive administrator
TTL is not vetoed merely because a response is HTTP 400 or above. Incomplete
standalone responses are not stored as complete pages.

Public searches (`s=`), REST GETs (`/wp-json/` and `rest_route`), XMLHttpRequest GETs,
and `ref=` are cache candidates. The original URL, query values and cookies still
reach the application on a miss. An internal copy of the URL omits known campaign
parameters (`utm_*`, `gclid`, `fbclid` and related click IDs) from the lookup key.
Different tracking IDs can reuse the same page. Functional parameters, including
search, language, currency and `ref`, remain distinct. Browser analytics still
see the original landing URL; PHP tracking on every landing needs a separate
tracking request/integration because PHP does not run on a cache HIT.
Private/no-store responses and response cookies without Shared approval
are delivered without sharing their bodies. Account/cart/checkout routes, cart
mutations, authentication/nonces, login and private session cookies remain private.
Store API cart/checkout reads are private too; public product REST reads can cache.

`Vary: Accept` retains real HTML/JSON/XML/image negotiation and `q=0`. An internal
copy normalizes equivalent unquoted header whitespace. Simple media lists also
share variants across token case and equivalent quality notation (`q=0.900` /
`q=0.9`, implicit quality 1 / `q=1.000`). Simple `Accept-Language` lists receive
the same treatment for language-tag case, spacing and quality notation. Both
original headers reach the origin; browsers retain the public `Vary` headers.
Different languages, weights and preference order remain distinct. Media
parameter values, quoted values and nonstandard syntax retain their existing
variation. These improvements work in Basic without any application plugin;
requests with other syntax continue normally without the extra normalization.
The rules follow [HTTP negotiation semantics](https://www.rfc-editor.org/rfc/rfc9110.html#section-12.4).
Recognized stored UltraCache HTML additionally groups
equivalent AVIF/WebP capabilities, so matching warmup/browser requests reuse the
same representation.
This includes Apache static snapshots and actual PHP page-cache responses marked
`X-Ultra-Cache: HIT`, including stored ESI parents. The existing public, cacheable,
variant and no-Set-Cookie conditions still apply. Newly rendered `STORE` responses
and other dynamic negotiation retain their real Accept dimensions.
With `Vary: Cookie`, an internal variant key omits only the known analytics IDs
listed in [`shared/cache-policy.vcl`](shared/cache-policy.vcl).
Unknown, consent, referral and language
cookies still select separate variants. Cookies are not stripped from origin
requests; downstream responses retain `Vary: Cookie`. Without an origin Vary,
ordinary unknown cookies do not cause a cache bypass.

Both `X-Hestia-Varnish` and `X-Cache` consistently report **HIT**, **MISS** or
**PASS**. `X-Hestia-Varnish-Reason` reports a concrete request/origin reason,
such as `cookie-policy-private`, `private-rest-context`, `origin-set-cookie`
or `origin-cache-policy`. Public hits/misses report `cached-response`/
`fetch-required`.

The shared file contains the request/privacy/session/ESI, representation and
lookup-key rules unchanged in both panel integrations. Hestia supplies the
host/backend, scoped tokens, native transport and administrator additions.
Each distribution includes the full file and works independently. See the
[shared contract](shared/CONTRACT.md) for hooks and canonical invalidation URLs.
Exact PURGE accepts any tracking URL; regex/batch BAN selects canonical lookup
URLs. The shared parity fixtures exercise both generated adapters.

The native `esi_ignore_other_elements` feature allows literal includes inside HTML
attributes to be composed as well as includes in inline JavaScript and JSON within HTML.
Fresh starts use the managed unit flag; upgrades add it through the authenticated
native CLI without restarting Varnish or replacing other runtime feature flags.
Parent privacy and private-fragment cookie rules remain unchanged. This does not
enable ESI for standalone JSON responses. Parents fetched before enabling the
parser feature retain their old parsed body until invalidated or refetched;
rewarm those pages through the application when testing the new nonce feature.

Basic's URL, cookie and header cache-key improvements work without UltraCache.
Basic does not enable ESI composition. The UltraCache preset can also compose
standard ESI from another application, but the application must produce the
includes, fragment endpoints and suitable cache policy. Enabling a Varnish parser
feature alone cannot turn ordinary WordPress nonces into private fragments.

## Cookie choices per website

Open **Plugins → Varnish → your domain → Cookie cache policies**. Each exact
cookie name or literal trailing-star prefix has independent Basic and UltraCache
**Shared HTML**, **Public variant** or **Private** actions. Website choices take
precedence over central choices; reset resumes inheritance. Cookies reach the
application unchanged. Origin private responses and private routes/actions have
separate exclusions.

Normal upgrade converts old **Cookies that bypass cache** entries into visible
Private rows with an import description. Existing explicit website choices keep
precedence independently in each profile. The old form and separate runtime PASS
list are removed. Imported rows can be edited/reset in the same cookie editor;
no second list overrides it. Tokens and other website settings are retained.

Existing static-file routing is retained: files served directly by Nginx remain
there. Both presets handle public assets that reach Varnish without changing routing.

## Change cache size in Hestia

1. Open **Plugins → Varnish → All accounts** as administrator.
2. Under **Server settings · all websites**, enter the **Varnish cache size (MiB)**,
   for example **8192** for 8 GiB shared by all sites.
3. Click **Apply size and restart Varnish**.

Changing size restarts Varnish and clears its cached content. The new size is
verified against the running Varnish process and retained through updates and backups.
An unchanged size does not restart the service.

## Change the server timeout in Hestia

1. Open **Plugins → Varnish** as administrator, in **All accounts**.
2. Under **Server settings · all websites**, enter **300** in
   **Backend first-byte timeout (seconds)**.
3. Click **Apply server timeout**.

This is the time Varnish allows Apache to start responding, including cache
bypasses. Leave the field blank to follow the loaded native Nginx hosting read
allowance. Saved explicit values, including zero and fractions, remain overrides.
The addon also inherits native connect/send/read allowances and gives its front
Nginx proxy and Varnish delivery enough time to complete the exchange. It does
not change Apache/PHP execution limits. Native changes are picked up at the next
reconciliation, including the existing discovery cron; no statistics collector
or application requests are needed. Managed timeout directives are excluded
from discovery, preventing cumulative growth on subsequent reconciliations.

## Static browser caching

Administrators: **All accounts → Browser cache · central defaults**. Owners:
**your domain → Browser cache**. Each domain can inherit central defaults or save
an override; aliases share its policy. Every control has mouse-over help.

Ordinary existing static files default to 30 days. Only declared content-hashed
paths receive the one-year `immutable` policy. Enter one path per line, for
example `/assets/app-{hash}.js`; `*` matches within a path segment. The UltraCache
profile automatically includes its CSS-bundle path without replacing custom
paths. A query such as `?ver=1` alone does not declare content immutable.

Zero seconds sends `no-cache` so browsers revalidate with ETag/Last-Modified.
Disabling headers removes the addon's static Cache-Control policy. Existing
files stay directly on Nginx, missing files retain the existing origin fallback,
and dynamic application responses keep their own headers. Native parent headers
are retained using `add_header_inherit merge`; an explicit custom parent
`add_header Cache-Control` remains a separate native policy and should not be
combined with an overlapping addon policy. These settings cannot
clear a copy already stored by a visitor: use a new/versioned URL when replacing
an asset that must update immediately.

## Central profile additions

Administrators can add supported request and backend-response VCL per profile.
These run before the corresponding site additions and retain tenant and response
privacy checks. Applying rules invalidates only sites whose effective profile
rules changed; other profiles keep their warm cache. The default-profile selector
only affects newly discovered domains, retaining existing assignments and the
existing Hestia enable/disable policy.

## UltraCache async cart

The UltraCache profile recognizes an origin-approved warmed public parent marked
`X-UltraCache-Woo-Async-Parent: 1`. With the existing explicit request opt-in,
cart/session visitors can HIT that parent and fetch their personal cart
asynchronously. A private cold miss still requires the established ESI handshake;
login, private cart endpoints, `private/no-store`, Set-Cookie and Vary separation
remain enforced. Ordinary unknown cookies and query strings do not create a
general cache bypass; functional query values remain separate cache keys.

Hover over controls to see their purpose and scope. **Show memory usage** reads
one native `varnishstat` snapshot only when clicked. It shows malloc cache storage
used/free and the configured budget, rather than total process RSS. There is no
background statistics collector, request-log analysis or automatic polling.

For VCL details, backup, restore, removal or importing an existing Varnish,
see the [administration reference](docs/administration.md).

See the [changelog](CHANGELOG.md) for completion, native controls and compatibility changes. Existing service budgets and credentials are preserved on update.

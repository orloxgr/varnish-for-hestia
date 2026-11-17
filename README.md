# Varnish for Hestia

One shared Varnish service, separate site caches and purge tokens, with per-site
profiles and VCL controls. Version **0.17.0** · GPL-3.0-or-later.

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

While this repository is private, cloning requires your GitHub username and a
token with repository access at the password prompt, not your GitHub password.

## Cookies on cached pages

**Cookie policies** opens the searchable editor. Administrators have central
choices under **All accounts**; account owners edit only their own websites.
The table shows stable IDs, literal cookie names/prefixes, descriptions, actual
actions, separate proposals, confidence and precedence. You can add rows, paste
tab-separated rows from Excel, select rows for bulk changes, and reset local
choices to the inherited policy. Save validates and compiles the actual VCL.

- **Automatic:** retain the existing handling for this match.
- **Shared HTML:** omit this value from Cookie variation, preserving the real
  cookie in the browser and origin request.
- **Public variant:** include the selected cookie pairs in lookup even without
  origin `Vary: Cookie`; tell downstream caches about Cookie variation too.
- **Private:** pass the request to the application and deliver it as no-store.

Site choices precede central choices; exact names precede longer-to-shorter
prefixes within each scope. Core login/session/cart and origin privacy still
apply. Database-derived estimates are labeled as inferred and require an
explicit choice; category labels never activate a policy. Upstream updates do
not overwrite saved choices. Only executable changes invalidate the affected
website cache; editing a description does not purge pages.

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

Under each website, **Cookies on cached pages** can deliver a missing Meta
`_fbp` separately from public cached HTML. Enable it only for an existing Meta
integration and enter the exact cookie/value that expresses the visitor's
current consent, such as `cmplz_marketing=allow` for an appropriate Complianz
configuration. This does not install Meta Pixel or change the consent manager. The native
issuer also respects Meta's explicit provider hold state. An available actual
provider endpoint remains authoritative for complex consent rules in either
profile.

Each consenting visitor receives their own cookie. Existing cookies, provider
renewals, deletions and all other Set-Cookie fields are preserved. Login/cart
privacy remains active. Basic works independently of UltraCache; UltraCache
also uses its trusted application approval and provider/CMP delivery owner.
Service-specific CMPs such as Real Cookie Banner use their actual provider API,
not a guessed category cookie. PHP/direct-origin and static-page delivery are
handled by the application integration.

A cold Basic response that sets a cookie still reaches its visitor unchanged;
there is no hidden warm-up. After public HTML has been cached, new visitors can
receive a HIT and an independent cookie. The native header VMOD preserves
separate Set-Cookie fields. When adding modules to an existing installation, the installer selects the
matching native ABI without replacing or restarting the running engine.

The reviewed cookie catalogue is local, versioned, and shared with Webuzo and
UltraCache. The separately attributed Open Cookie Database snapshot is for
recognition; its categories do not automatically authorize caching or issuing
cookies. Unknown cookies do not gain a new automatic bypass rule.

The bundled assessment file covers 2,288 source records: 46 match existing
reviewed policies and 2,242 are explicitly labeled low-confidence inferences.
These estimates describe possible initial server HTML effects; they are not
independent verification of each provider or a source of automatic new rules.
Maintainers can reproduce the editorial file with
`tools/build-cookie-assessments.py --source open-cookie-database.csv --revision <upstream-commit> --output assessments.json`.
The tool records the source SHA-256, revision, reasons and confidence. It does
not download data, change installed settings or activate its suggestions.

### Automatic recognition database updates

Administrators: **All accounts → Cookie recognition database**. Daily updates
are enabled by default. **Update now** checks immediately, even when automatic
updates are disabled. The panel shows the upstream revision, record count, last
attempt, successful check, database update and any failure. Opening the panel or
saving the switch does not download anything.

Updates fetch the original Open Cookie Database repository directly: read its
current commit, then download that exact revision's CSV and Apache-2.0 license.
The snapshot and preference live under
`/var/lib/varnish-for-hestia/cookie-recognition/`, independently of installed code,
and survive plugin updates. A host-specific minute in the 03:00 local-server
hour spreads daily checks across installations, using the existing managed cron
file. Root can also run `v-varnish-hestia update-cookie-database` to execute the
scheduled operation, which respects the automatic-update switch.

Downloads use verified HTTPS, fixed endpoints and no redirects. Untrusted input
has explicit safety bounds: 32 MiB CSV, 1 MiB revision/license responses, 100,000
records, 128 columns per row and 256 KiB characters per field. The column count
is checked before allocating CSV field arrays. UTF-8, CSV structure, columns, wildcard
values and control characters are validated. Valid Unicode and optional empty
provider metadata are retained. The download SHA256 records byte identity; it
is not an independent upstream signature. The last valid snapshot remains on
download/validation failure, with a visible error. Status reads do not wait on
the download lock; downloads never hold the Varnish operation lock.

This updates **recognition metadata only**, for both presets. It does not change
reviewed executable policies, site cookie overrides, consent or provider issuance;
it does not reload VCL, restart services, purge or warm pages. Runtime visitor
requests do not contact GitHub and no visitor cookie values are uploaded.

Inspect `X-Cache-Cookie-Names`, `X-Cache-Cookie-Role`,
`X-Cache-Cookie-Policy` and `X-Cache-Cookie-Delivery` beside `X-Cache` to see the
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

There is no addon TTL cap or forced grace/keep duration. Freshness follows the
origin and native Varnish, with explicit central/site VCL additions retained.
Uncacheable-response markers use the running Varnish's `uncacheable_ttl` setting.
Ordinary Set-Cookie responses remain uncacheable in Varnish without rewriting
the origin's Cache-Control. Personal ESI/session responses retain their privacy
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
Set-Cookie and private/no-store responses
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
such as `woocommerce-session-cookie`, `private-rest-context`, `origin-set-cookie`
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

## Cookie exclusions per website

Open **Plugins → Varnish → your domain → Cookies that bypass cache**.
Enter one cookie name per line, such as `custom_currency`, or a prefix such as
`membership_*`, then click **Save cookie rules**. Empty uses the built-in defaults.

Both presets bypass known login, session and cart cookies; other cookies do not
cause bypass by themselves. Add rules for applications that personalize HTML
without declaring a suitable Vary or private response policy. Both presets also
handle ordinary public HTML/CSS/HTTP content.
Rules apply to the selected domain and aliases. Administrators use the same
controls through **Manage website**. Cookies are not deleted.

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

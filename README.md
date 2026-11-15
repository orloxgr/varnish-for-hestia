# Varnish for Hestia

One shared Varnish service, separate site caches and purge tokens, with per-site
profiles and VCL controls. Version **0.15.1** · GPL-3.0-or-later.

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
The final machine-readable JSON stays on stdout. Panel/API and cron operations
remain quiet. To keep both progress and the result in a local terminal log:

```sh
set -o pipefail
sudo python3 /usr/local/src/varnish-for-hestia/tools/install.py 2>&1 | tee varnish-install.log
```

Version **0.15.1** provides two presets with one common request/response policy.
Existing General, WordPress and WooCommerce selections become Basic automatically.
Site IDs, tokens, enable settings, cookie rules, browser settings and local VCL
are retained. Former central profile rules are prepended to the corresponding
sites' local VCL, retaining their original scope and execution order. UltraCache
selections and their central rules remain UltraCache. The conversion is idempotent.

The installer regenerates the VCL and managed domain routes. Upgrading from
before 0.15.0 starts that version's new cache namespace; 0.15.1 retains the
0.15.0 namespace and warm public objects. No Varnish restart or manual domain
rebuild is needed. Refresh Hestia with **Ctrl+F5**.

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
headers. HTTP status alone does not impose an additional addon caching veto.

Public searches (`s=`), REST GETs (`/wp-json/` and `rest_route`), XMLHttpRequest GETs,
and `ref=` are cache candidates. The original URL, query values and cookies still
reach the application on a miss. All query parameters, including campaign and
referral parameters, remain distinct cache keys: attribution is not discarded or
silently merged into another referral. Set-Cookie and private/no-store responses
are delivered without sharing their bodies. Account/cart/checkout routes, cart
mutations, authentication/nonces, login and private session cookies remain private.
Store API cart/checkout reads are private too; public product REST reads can cache.

Native `Vary: Accept` retains real HTML/JSON/XML/image negotiation and `q=0`.
Only equivalent unquoted header whitespace is normalized; different media
preferences are not guessed to be equivalent. With `Vary: Cookie`, a private
internal variant key omits only the known analytics IDs listed in
[`cookie_policy.py`](src/cookie_policy.py). Unknown, consent, referral and language
cookies still select separate variants. Cookies are not stripped from origin
requests; downstream responses retain `Vary: Cookie`. Without an origin Vary,
ordinary unknown cookies do not cause a cache bypass.

Both `X-Hestia-Varnish` and `X-Cache` consistently report **HIT**, **MISS** or
**PASS**. `X-Hestia-Varnish-Reason` reports a concrete request/origin reason,
such as `cart-session`, `private-rest-route`, `origin-set-cookie` or
`origin-cache-control`. Public hits/misses report `cache-hit`/`cache-miss`.

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

# Site settings and cookie policies

This guide describes the controls under **Hestia → Plugins → Varnish**.
For installation and profile selection, see the [README](../README.md).
For backup, restore, adoption and removal, see [Administration](administration.md).

## Profiles and scope

Basic works without a WordPress plugin and does not compose ESI. The UltraCache
profile on WordPress requires the compatible UltraCache plugin and its working
Varnish connection. Keep a site on Basic until that integration is configured.

Administrators see all accounts and websites. Owners manage their own websites.
Central profile additions apply before corresponding site VCL additions; the
default-profile selector affects newly discovered domains, not existing choices.
Applying changed profile rules invalidates the affected sites rather than every
profile's cache.

## Server cache and CMS rules

Each website has **Server cache and CMS rules**. **Enable aggressive caching**
is off by default and works with either profile. When enabled, eligible anonymous
HTML uses the chosen positive **Server cache duration (seconds)** even when
generic origin cache headers request private/no-store or a shorter lifetime.
Original browser cache headers are restored on delivery.

This setting does not change cookie actions. Explicit Private choices and
private routes/actions retain their handling. Original request URLs and cookies
reach the application unchanged. HTML is cached as supplied, including embedded
tokens; the setting does not verify an opaque session or personalize tokens.
Use the application's fragment integration when that content must vary privately.

CMS detection uses Hestia's native document root, including custom roots and
nested installations. Known WordPress/WooCommerce, Joomla, Drupal, Magento and
PrestaShop routes are included. Where available, static backend aliases and
read-only database route metadata enrich those rules. Detection retains the
last valid configured routes when metadata fails.

- **Additional private path prefixes:** custom URL prefixes, one per line.
- **Excluded CMS directories:** literal paths relative to the website's document
  root, such as `/old-site/httpdocs`. The whole subtree is skipped before config
  reads or database queries. `/` excludes all CMS detection for this website.
- **Refresh CMS detection:** rereads metadata as the hosting account without
  running customer PHP. Installing or saving cache behavior can also refresh it.

Excluding a directory removes its detected routes and cookie names; it does not
delete files, edit database settings or block URL access. Normal panel reads
and minute reconciliation do not recursively scan sites or query route databases.
A changed native document root triggers a refresh; failed discovery after that
change pauses that website's cache until detection succeeds.

Root can explicitly refresh detection for all websites:

```sh
sudo /usr/local/hestia/bin/v-varnish-hestia refresh-cms
```

## Cookie policy editor

Administrators edit central choices under **All accounts → Cookie policies**.
Owners open a website's **Cookie cache policies**. The table supports search,
independent Basic/UltraCache action filters, editable descriptions, custom rows,
tab-separated spreadsheet paste, bulk selections and reset to inherited choices.
Internal IDs are hidden; **Why / precedence** opens the full explanation.

Each profile independently chooses Shared, Vary or Private. The current panel
labels the first two actions **Shared HTML** and **Public variant**. Site choices
precede central choices, then bundled defaults. Within a scope, exact names
precede matching prefixes, with longer prefixes before shorter ones. Only a
trailing `*` is interpreted as a prefix wildcard. A prefix does not inherit the
decision of an arbitrary child cookie.

Shared omits the cookie's value from page variation while preserving the
original application request. Vary includes the selected cookie pairs in lookup
and retains downstream Cookie variation. Private passes matching requests to
the application with no-store delivery. These choices do not turn a private
application route into a public page.

When every response Set-Cookie field is approved as Shared, otherwise eligible
HTML can be stored without those fields. The original fields go only to the
visitor whose request caused the fetch. Duplicate fields, attributes, renewal
and deletion are retained. Later HITs never replay those personal cookie values.
Actual issuance on a HIT uses the provider's supported browser/application
delivery path. The proxy does not generate provider IDs or grant consent;
Meta `_fbp` follows the same editor and rules as other cookies.

Every bundled row has an executable decision. Evidence/confidence labels
describe the basis for that choice, not whether the rule runs. Saved central and
website choices survive addon updates. Only executable policy changes invalidate
affected site caches; editing a description alone does not purge pages.

### Bundled data

Recognition descriptions and executable defaults ship together in a reviewed
addon version. The central **Cookie database · reviewed rules** section shows
the source revision, record count and rules version. Update the addon to receive
a new bundle; there is no separate daily database download or update button.

The original recognition dataset is
[Open Cookie Database](https://github.com/jkwakman/Open-Cookie-Database), licensed
Apache-2.0. Its categories alone do not determine executable cache actions.
Maintainers regenerate the reviewed bundle with the
[bundle generator](../tools/build-cookie-assessments.py). The
[Cookie Control contract](../shared/COOKIE-CONTROL.md) describes application
synchronization; neither is a separate website database-update procedure.

### WordPress synchronization

In the site's cookie editor, expand **WordPress integration** only after
installing the compatible UltraCache plugin and configuring the same site token.
The control endpoint is on this website or an owned alias:

```text
https://example.com/wp-json/ultracache/v1/cookie-policy-control
```

Enable **Synchronize policies with UltraCache WordPress**, then Save & apply.
The active profile's choices synchronize with the application's supported PHP,
drop-in and Apache Static consumers. The other profile column stays independent.
The signed prepare/commit transaction keeps native/application changes coherent;
a failed operation reports its stage and retains the previous configuration.

The committed application snapshot stays in effect until another successful
synchronization. Disabling the connection clears managed ownership and returns
the WordPress runtime to its standalone defaults. It does not remove the choices
saved in the Hestia panel.

An owner can inspect or reset the managed application snapshot using WP-CLI in
the actual site's environment:

```sh
wp ultracache cookie-policy status --format=json
wp ultracache cookie-policy reset --format=json
```

Reset invalidates the configured native site; an explicit Save in Hestia can
reapply the saved panel choices. This connection synchronizes policy; it does
not manufacture cookie issuers or add provider support to an unrelated plugin.

## Server controls

In **All accounts → Server settings · all websites**:

- **Varnish cache size (MiB):** one shared storage budget for all sites.
  **Apply size and restart Varnish** restarts the service and empties cached
  content. An unchanged size does not restart it. Updates retain the saved size.
- **Backend first-byte timeout (seconds):** how long Varnish waits for Apache
  to start responding, including bypasses. Blank follows the native hosting read
  allowance. Explicit zero/fractional values remain overrides. This does not
  change Apache/PHP execution limits.
- **Show memory usage:** reads one native `varnishstat` snapshot on demand.
  It reports malloc cache storage used/free and budget, not total process RSS.
  There is no background statistics collector or automatic polling.

Timeout changes apply through ordinary reconciliation without restarting Varnish
or purging solely because the timeout changed. Managed proxy allowances track
native connect/send/read settings without cumulative growth on each reconcile.

## Static browser caching

Administrators edit **Browser cache · central defaults**; websites can inherit
those settings or override them under **Browser cache**. Aliases share the policy.

Ordinary existing static files default to 30 days. Only declared content-hashed
paths get a one-year immutable policy, for example `/assets/app-{hash}.js`.
`*` matches within a path segment; `?ver=1` alone does not declare immutability.
The UltraCache profile includes its CSS-bundle path without replacing custom
paths. Zero seconds requests browser revalidation with ETag/Last-Modified.
Disabling headers removes the addon's static Cache-Control policy.

Existing static files remain directly on Nginx and missing files keep the
origin fallback. Dynamic application responses keep their own headers.
Avoid overlapping custom parent Cache-Control rules. These settings cannot
remove an already-stored browser copy; use a new/versioned asset URL for an
immediate content replacement.

## Cache diagnostics

`X-Cache` and `X-Hestia-Varnish` report HIT, MISS or PASS.
`X-Hestia-Varnish-Reason` explains the decision, such as
`cookie-policy-private`, `private-rest-context`, `origin-set-cookie`,
`origin-cache-policy`, `cached-response` or `fetch-required`.
Cookie-policy diagnostics report names/actions rather than cookie values.

A parent HIT alone does not prove that personal-fragment delivery used no
origin requests. Native/backend and application evidence are separate; see
the [shared contract](../shared/CONTRACT.md) and
[testing reference](testing.md) for implementation-level verification.

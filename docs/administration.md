# Administration reference

One native Varnish service for Hestia hosting accounts, with site-scoped tokens,
two presets, owner VCL editing and automatic native account/domain discovery.
The addon adds its own files and templates; existing Hestia scripts, pages and
vendor templates are not changed.

Source repository: [orloxgr/varnish-for-hestia](https://github.com/orloxgr/varnish-for-hestia).

For installation, profile selection and normal updates, see the
[README](../README.md). Detailed website controls are in
[Site settings and cookie policies](site-settings.md).

## Server controls

In **Plugins → Varnish → All accounts**, the administrator can set **Backend
first-byte timeout (seconds)** for all current and future domains. The field
accepts finite nonnegative seconds, including fractions; blank follows hosting.
`300` allows a five-minute wait for the origin's first
response byte. The setting is stored in the root-private desired/applied state
and compiled as `.first_byte_timeout` on every generated VCL backend. The native
global `varnishadm param.show first_byte_timeout` value remains unchanged; the
backend-specific VCL setting takes precedence. Nginx, Apache and PHP limits are
independent.

Saving validates and activates a VCL generation using the existing configuration
transaction. It does not restart the service or invalidate sites solely because
the timeout changed. Owners cannot modify this server setting.

**Varnish cache size (MiB)** controls the shared malloc storage budget for all
accounts and domains (a positive number of MiB, validated by the native service). **Apply size and restart Varnish** updates
only the addon's existing native service drop-in and `settings.json`, reloads
systemd, restarts Varnish and verifies the size in the running native manager's
startup arguments. A restart clears cached content; VCL, tokens and site settings
remain.
Saving the existing size does not restart. Updates and configuration archives
retain the saved size.

A private `resize.json` undo record restores the previous files and restarts the
previous size if applying fails. An interrupted resize is recovered by the next
addon operation/settings read. If recovery also fails, its journal remains for
a retry and the operation reports failure. No additional service is installed.

**Show memory usage** is a read-only action. It runs `varnishstat -1 -j` once,
returns only `SMA.s0.g_bytes` and `SMA.s0.g_space` plus the configured memory budget,
and does not run policy synchronization. These are cache storage counters, not
the total RAM usage of the Varnish processes. Mouse-over text explains controls.

## Installation details

Initial verified platform: **Ubuntu 26.04 amd64, Hestia 1.10.5, Varnish 9.1.0**,
with Nginx -> Apache/PHP-FPM. Install Hestia first, then clone the repository
into the retained source checkout:

```sh
sudo git clone https://github.com/orloxgr/varnish-for-hestia.git /usr/local/src/varnish-for-hestia
cd /usr/local/src/varnish-for-hestia
sudo python3 tools/install.py --memory-mb 1024
```

Keep `/usr/local/src/varnish-for-hestia` for future updates and recovery.

With no existing Varnish, the installer uses the official signed Ubuntu repository
and its signed APT candidate, with separate addon-owned repository files.
The example command sets a 1 GiB shared cache budget; choose a size appropriate
for the server. Rerun without memory options to update
addon files/templates and reconcile accounts, preserving credentials and choices.
Complete code generations live in `/opt/varnish-for-hestia.releases/`; an atomic
`/opt/varnish-for-hestia` pointer selects the active version. A failed ordinary
upgrade restores the previous code pointer and service settings. Interrupted
publication leaves a complete generation; repeat the same installer to finish:


```sh
sudo git -C /usr/local/src/varnish-for-hestia pull --ff-only
sudo python3 /usr/local/src/varnish-for-hestia/tools/install.py
```

An unmanaged existing Varnish requires explicit adoption, described below.

If initial installation is interrupted or APT/startup fails, run the same install
command again. Its private transaction retains identities, personal tokens and
the administrator secret, including when the package has already been installed.
The native package's automatic first start is delayed by a temporary addon-owned
unit condition until credentials and group permissions are ready. The condition
is removed when installation commits; no separate service or global package-start
policy is introduced.

## Open the owner interface

After signing into Hestia, open:

```text
https://YOUR-SERVER:8083/plugins/varnish/
```

Direct bookmarks first show an **Open Varnish for Hestia** link, retaining Hestia's
native same-origin/session policy. The top-bar **Plugins** menu is loaded from an addon-owned script in
`/usr/local/hestia/web/js/custom_scripts/`. Existing menu files are not modified.
Administrators see all accounts and websites on the addon home page. Select
accounts or individual websites for bulk changes, or choose **All accounts / websites**.
Account selections include every website belonging to those accounts. **Manage account**
and **Manage website** open the existing owner controls without impersonation.
Varnish profile changes preserve each site's optional VCL sections and purge token.
Bulk website enable/disable retains the separate account enable/disable choice.
Native hosting suspension and package restrictions continue to apply.
Bulk changes affect the current websites; newly discovered sites use the
configured default profile, initially Basic.

Each owner can:

- Select Basic or UltraCache per site.
- Edit the site's request and backend-response VCL sections.
- View/change only that site's HTTP purge token and clear its cache/aliases.
- Disable one site or the whole account, retaining individual site choices.

The selector does not verify that the application is installed or connected.
Basic works without a WordPress plugin. On WordPress, select UltraCache only
after installing, enabling and connecting the compatible UltraCache plugin;
otherwise its personal-content delivery contract is unavailable and requests
can fail or behave incorrectly. Configure the application's Varnish connection
with the website token. Optional cookie-policy synchronization is an explicit
connection described in the [site settings guide](site-settings.md#wordpress-synchronization).
HTTP purge uses
`127.0.0.1:6081`, the selected domain's Host header, and either
`X-Hestia-Varnish-Token` or `X-UltraCache-Token`. The global administrator secret is
never provided to a hosting user. Personal tokens contain 12-256 letters, digits,
underscores or hyphens.

## VCL and isolation

Hostnames and aliases are assigned stable site scopes, with native Apache origin
IP/NAT mappings. Cache keys remain isolated between sites and HTTP/HTTPS variants.
Exact PURGE invalidates both protocol variants; BAN is composed by the server for
the authenticated site and its aliases. Caller-supplied BAN expressions are ignored.
Public proxy requests cannot use either invalidation method.

Basic and UltraCache share common HTTP/WordPress/WooCommerce policy code, with
independent cookie choices. Public search, REST GET, XMLHttpRequest GET and
referral parameters do not cause PASS merely by name. Original query values
reach the origin; an internal lookup URL omits known campaign parameters while
keeping functional distinctions. Private routes and actions retain their handling.
In Basic, response eligibility follows HTTP policy and the selected cookie
actions unless the site's aggressive mode is explicitly enabled. In UltraCache,
approved output uses its application storage/TTL contract and supported personal
fragment integration while preserving browser headers. Shared response-cookie
values are delivered only to their visitor and never replayed from shared storage.

Static files served directly by Nginx retain their existing routing. Public HTML,
CSS and other assets that reach Varnish use the selected preset's cache policy.
The UltraCache profile adds server-side ESI composition, cached personal
fragments and explicitly approved async parents through the compatible
application. Basic does not enable ESI. See the
[profile comparison](../README.md#basic-vs-ultracache).

### Cookie choices and imported exclusions

Use **Cookie cache policies** for exact names and trailing-star prefixes. Each
profile has an independent Shared HTML, Public variant or Private action.
Website choices precede central choices; within a scope exact names precede the
longest matching prefix. Original cookies reach the application unchanged.

Ordinary upgrade imports old website bypass entries as visible Private choices,
with a source description. A covering explicit website choice wins independently
per profile. A wider imported prefix remains active outside a newer, narrower
choice. The usual site-over-central precedence remains visible; central rules
are not copied into websites or frozen by migration. Tokens and unrelated
settings remain unchanged. Repeating the upgrade does not recreate imported rows.

The separate bypass form and runtime list are retired. Imported rules use the
same request/response resolver and connected WordPress snapshot as other editor
rows. Resetting a row resumes the ordinary inherited default; it does not restore
a hidden old exclusion. Existing backups remain validated and can be restored
through normal migration. Real private routes/actions and origin privacy remain
separate from cookie choices.

## Native routing and lifecycle

An addon-owned root cron entry reconciles once per minute; owner actions also
reconcile immediately. Hestia remains authoritative for packages, users, domains,
aliases, suspension and deletion. Rebuilds, aliases and ordinary Hestia password
changes preserve cache tokens. Replacement accounts receive new identities.

Enabling selects an additional `hvh-varnish-<revision>` proxy template. Disabling
restores the site's saved original proxy template. Native Hestia commands generate
the vhosts; no vendor scripts/templates are patched. Immutable template versions
allow a failed update to restore the previous selection. The apply operation waits
for Nginx's native worker turnover. Configuration updates have a private durable
undo journal. A killed writer is recovered on the next reconciliation, including
VCL, native routes and stored choices. Recovery can restart the native cache;
ordinary changes and rejected VCL do not restart it. A stopped cache falls back to Apache through
the Nginx upstream. TLS metadata reaches PHP using the existing Hestia per-vhost
`/etc/apache2/conf.d/*.inc` include point, limited to native local proxy peers.

Native suspension disables cache access; native unsuspend/rebuild restores the
owner's retained choices. A proxy-template change made directly in Hestia is
recognized as opting that site out. Root administrators may set `allowed_packages`
(null means all) and `denied_packages` in private `settings.json`; owners cannot
bypass those package restrictions.

For immediate root reconciliation:

```sh
sudo /usr/local/hestia/bin/v-varnish-hestia reconcile
```

Addon-owned files live under `/opt/varnish-for-hestia/`,
`/etc/varnish-for-hestia/`, `/var/lib/varnish-for-hestia/`,
`/etc/cron.d/varnish-for-hestia`, and the root-private runtime lock directory
`/run/varnish-for-hestia/`. Additional Hestia templates and the Apache include are
also addon-owned. A drop-in configures the packaged Varnish unit; original unit,
VCL and administrator secret files are retained. No firewall, SSH or login
settings are changed.

## Adopt an existing native cache

Create a root-owned mode-600 manifest. Explicitly describe existing cached sites,
retained personal tokens/profiles and the original direct-origin proxy template:

```json
{
  "schema": 1,
  "admin_secret_file": "/etc/varnish/secret",
  "sites": {
    "alice": {
      "example.com": {
        "profile": "ultracache",
        "token": "EXISTING_SITE_TOKEN",
        "original_template": "default"
      }
    }
  }
}
```

```sh
sudo chmod 600 /root/varnish-adoption.json
sudo python3 /usr/local/src/varnish-for-hestia/tools/install.py --adopt /root/varnish-adoption.json --memory-mb 8192
```

The installer authenticates to the existing local management interface, preserves
those site tokens, configures its separate private service files and selects the
additional templates. Existing applications are not inspected or reconfigured.
The existing native cache must be running and its administrator secret available.

## Back up, restore or remove

Keep the retained checkout at `/usr/local/src/varnish-for-hestia`, outside the installed
`/opt/varnish-for-hestia/` directory. An administrator can run:

```sh
sudo install -d -m 700 /root/varnish-recovery
sudo python3 /usr/local/src/varnish-for-hestia/tools/manage.py backup /root/varnish-recovery/config.json
sudo python3 /usr/local/src/varnish-for-hestia/tools/manage.py restore /root/varnish-recovery/config.json
sudo python3 /usr/local/src/varnish-for-hestia/tools/manage.py uninstall /root/varnish-recovery/before-removal.json
```

Archives contain service settings, the administrator secret, personal purge
tokens, profiles, custom VCL, site choices and any addon-owned official APT
source/key record. They are root-owned mode-600 files
and never overwrite an existing archive. Keep them private. Cache contents and
application files are excluded.

Restore requires the supported native package and the original Hestia proxy
templates. Restore native Hestia accounts before the addon archive. Keep this
separate addon archive alongside the Hestia backups; native account archives do
not include the shared cache registry. It binds archived identities to current Hestia usernames, discovers
new accounts, compiles VCL before service changes and restarts with an empty
cache. A failed start restores the previous service configuration. If the restore process
is killed, repeat that same restore command: a private undo record recovers the
previous configuration before retrying. Owner actions wait until root finishes
the restore. Restore also
works after full removal, using the retained checkout and archive.

Uninstall creates its recovery archive first, restores original proxy templates
for active and suspended domains, stops/disables Varnish and removes addon-owned
code, state, integration, templates and its own APT source/key files. Existing
repository files are retained. Suspended accounts stay suspended. For
those accounts the addon uses Hestia 1.10.5's native rendering and metadata
functions, since its template-changing CLI rejects suspended accounts. The native
package and pre-existing native configuration are retained; another configuration
is not started implicitly. Existing Hestia scripts/templates are never patched.

## Compatibility and operating limits

Supported versions: Ubuntu 26.04 amd64 / Hestia 1.10.5 / Varnish 9.1.0.
Fresh installations use the signed APT candidate from the matching official
Ubuntu resolute repository, without an addon version pin. Existing installations
retain their native package. Generated VCL is checked by the installed native
compiler before activation; invalid configuration is not published.
Initial support is the native Hestia Nginx/Apache/PHP-FPM layout and standard
Apache templates containing the include point above. Original proxy-template
selection is saved; directives embedded only in a previous custom template are
restored on disable. The shared process shares CPU/RAM/availability, without
per-owner resource quotas. Request traffic uses the previous VCL while compiling
a configuration update.

A domain with no native proxy remains in that topology. Native proxy enablement
is discovered and its original template is saved before cache routing is selected.
Restoring addon settings uses the current Hestia domain inventory; it does not
recreate deleted domains or change an independently removed proxy into a new one.

## HTTP cache control

Use the site's displayed purge token and public Host header with the local
Varnish listener. `PURGE /path?query` invalidates that exact URL across its Vary
representations. `BAN` accepts the generated UltraCache host plus anchored URL
expression, a batch of anchored URLs, HTML-only selector, or explicit whole-host
selector. Every operation is also constrained to the authenticated site's
immutable identity. Malformed expressions are rejected rather than broadened.

UltraCache HTTP contract **v2** is advertised as **ultracache-hestia-v2**. Its
authenticated capabilities are `exact-purge`, `exact-ban`, `batch-ban`, `html-ban`
and `host-ban`, plus native `soft-purge`. ESI is an
independent HTTP behavior enabled by the UltraCache profile's response handshake.
Older UltraCache clients can continue using portable HTTP PURGE and BAN.

Updating preserves tokens, VCL sections and the configured memory budget.
Version 0.15.0 converts the former General/WordPress/WooCommerce selections to
Basic and keeps UltraCache. Previous central additions are folded into each
corresponding site's local additions, in their original order. There are only
two selectable/runtime presets after this idempotent conversion. The policy
uses a fresh cache namespace; pages refill on demand without restarting Varnish.
Protocol and content negotiation remain Vary variants, so exact PURGE removes
them together. The origin's TTL/grace policy remains authoritative.

Version 0.16.0 includes `shared/cache-policy.vcl` unchanged from the Webuzo
integration. Hestia's adapter retains host/backend/token isolation, native
transport and explicit administrator additions; application, ESI, privacy,
representation and lookup-key rules are defined only in the shared file.
The complete shared directory is part of atomic addon code publication.

Version 0.16.2 also recognizes an actual origin `X-Ultra-Cache: HIT` as stored
HTML, alongside Apache static snapshots, for equivalent browser Accept reuse.
This includes PHP-served ESI parents. It retains public/cacheable/status/HTML,
image-variant and no-Set-Cookie checks, and the existing private-fragment rules.
A new dynamic `STORE` response still varies on its real Accept header.

Tracking parameters are omitted from an internal lookup URL, while the original
URL/Cookie remain available to the application on a MISS. Functional query values
and functional Cookie variations remain distinct. Exact HTTP PURGE maps tracking
URLs to the same canonical object within site/host scope. Exact/batch/regex BAN
expressions target canonical lookup URLs in `X-Cache-Object-URL`; the URL
normalizer is not applied to arbitrary regex source. Soft purge uses the same
key and follows native grace/background refresh. See [the shared contract](../shared/CONTRACT.md).

The new representation/key policy uses a fresh cache namespace without a native
service restart. The shared source and parity checks are local distribution/
development files, with no runtime dependency on another repository or network.

## Development checks

```sh
python3 tests/test_registry.py
python3 tests/test_fragments.py
python3 -m unittest discover -s tests -p 'test_http_control.py' -v
python3 -m unittest discover -s tests -p 'test_nonce_esi.py' -v
python3 tests/shared_policy_parity.py --adapter tests/parity_adapter.py --output parity-results.json
```

The registry and fragment-parser suites run without a live hosting installation.
VCL integration testing can use native `varnishtest` with isolated HTTP origins.
The nonce suite checks the generated service feature flags, additive runtime
activation and private-fragment composition in inline JS, JSON and attributes.

## License and upstream

GPL-3.0-or-later; see `LICENSE` and `CHANGELOG.md`.

- [Hestia web templates](https://hestiacp.com/docs/server-administration/web-templates)
- [Varnish CLI](https://varnish-cache.org/docs/7.4/users-guide/run_cli.html)
- [Apache FastCGI environment controls](https://httpd.apache.org/docs/2.4/mod/mod_proxy_fcgi.html#proxyfcgisetenvif)

## Panel menu

Hestia automatically includes the addon-owned `varnish-for-hestia.js` script from
`/usr/local/hestia/web/js/custom_scripts/`. Installed addons share one **Plugins**
dropdown; each installer and uninstaller manages only its own script. Native
Hestia login, account context and permission checks continue to apply. If the
header layout is unfamiliar, the script leaves the page alone; the direct
`/plugins/varnish/` URL remains available.

See [Hestia’s custom-script extension point](https://github.com/hestiacp/hestiacp/blob/1.10.5/web/js/custom_scripts/README.txt).

## Administrative completion and native compatibility (0.13.0)

Addon transport, managed files and configuration backups are not truncated by
addon byte ceilings. Commands, authenticated CLI operations, downloads and health
checks have no separate addon elapsed-work deadline. Native failure, invalid
configuration, authentication failure and cancellation remain real stop conditions.

Initial installation supports `--listen-port` and `--admin-port` for distinct
loopback TCP listeners. Existing configured ports are retained on update, and
owned Nginx templates use the configured listener. Restore checks schema,
checksums, ownership and native VCL compilation instead of an exact service-version
string. Fresh installs still use the signed repository and selected package.

Authenticated `PURGE` with `X-Purge: soft`, or contract-v2 `soft-purge`, expires
only the selected URL's variants, retaining native grace/keep. An eligible stale
object can be delivered while it refreshes; soft purge is not hard deletion.
Missing objects return success without an origin fetch. Invalid tokens and
cross-host operations remain denied.

First-byte timeout accepts finite nonnegative seconds, including fractions. On the tested native release, zero means immediate timeout; it does not mean unlimited waiting. Existing values are retained on update.

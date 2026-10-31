# Administration reference

One native Varnish service for Hestia hosting accounts, with site-scoped tokens,
four profiles, owner VCL editing and automatic native account/domain discovery.
The addon adds its own files and templates; existing Hestia scripts, pages and
vendor templates are not changed.

Version **0.5.0**.

Source repository: [orloxgr/varnish-for-hestia](https://github.com/orloxgr/varnish-for-hestia).

For the four-step installation, see [Quick start](../README.md#quick-start).

## Installation details

Initial verified platform: **Ubuntu 26.04 amd64, Hestia 1.10.5, Varnish 9.1.0**,
with Nginx -> Apache/PHP-FPM. Install Hestia first, then clone the repository
into the retained source checkout:

```sh
sudo git clone https://github.com/orloxgr/varnish-for-hestia.git /usr/local/src/varnish-for-hestia
cd /usr/local/src/varnish-for-hestia
sudo python3 tools/install.py --memory-mb 8192
```

Use GitHub credentials with repository access when cloning or updating a private
repository. Keep `/usr/local/src/varnish-for-hestia` for future updates and recovery.

With no existing Varnish, the installer uses the official signed Ubuntu repository
and pinned package `9.1.0-2~resolute`, with separate addon-owned repository files.
The quick-start command sets an 8 GiB shared cache budget. Rerun without memory options to update
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
native same-origin/session policy. Existing menu files are not modified.
Administrators use Hestia's account impersonation to manage a selected owner.

Each owner can:

- Select General, WordPress, WooCommerce or UltraCache for Hestia per site.
- Edit the site's request and backend-response VCL sections.
- View/change only that site's HTTP purge token and clear its cache/aliases.
- Disable one site or the whole account, retaining individual site choices.

Every profile is selectable without inspecting installed applications, plugins or
application connections. The selected profile is not automatically replaced or
disabled based on application presence or connectivity. No WordPress/UltraCache
files, settings or credentials are changed. Applications configure their
connections separately. HTTP purge uses
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

General respects request cookies/authentication and origin privacy headers.
WordPress adds private administration/API paths; WooCommerce adds cart, checkout
and account/action paths. UltraCache uses a WordPress/WooCommerce VCL profile with ESI, approved
shared parents, private cookie carriers, canonical image representation variants,
grace and keep. ESI can use the same site's aliases and cannot cross site scopes.

The site-local language supports `if`/`else`, request-side `return(pass)`, custom
`X-User-*` headers, and backend-response TTL/grace/keep values. For example:

```vcl
# Request section
if (req.url ~ "^/uncached/") { return (pass); }
```

```vcl
# Backend response section
if (bereq.url ~ "[.]css$") { set beresp.ttl = 2d; }
```

Input is parsed into this bounded language and compiled by native Varnish before
activation. Host/backend assignment, cookies/authentication fields, internal
scopes, global subroutines, imports/includes, inline C, purge logic and private
response controls stay outside the editing scope. Sections are limited to 16 KiB
and bounded expression/condition nesting. Invalid input keeps the working VCL,
state and routes. Routine changes use native `vcl.load`/`vcl.use`, without restarting
the shared service, and invalidate only affected site scopes.

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
The installer uses the verified package version; a future unknown major release
requires an addon update and is not an automatic compatibility promise.
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

## Development checks

```sh
python3 tests/test_registry.py
python3 tests/test_fragments.py
```

The registry and fragment-parser suites run without a live hosting installation.
VCL integration testing can use native `varnishtest` with isolated HTTP origins.

## License and upstream

GPL-3.0-or-later; see `LICENSE` and `CHANGELOG.md`.

- [Hestia web templates](https://hestiacp.com/docs/server-administration/web-templates)
- [Varnish CLI](https://varnish-cache.org/docs/7.4/users-guide/run_cli.html)
- [Apache FastCGI environment controls](https://httpd.apache.org/docs/2.4/mod/mod_proxy_fcgi.html#proxyfcgisetenvif)

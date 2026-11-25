# Varnish for Hestia

Manage Varnish caching from HestiaCP. The addon places one shared Varnish service
between Nginx and Apache/PHP-FPM, with separate website caches, purge tokens,
cookie policies and per-site profiles. Administrators manage all accounts;
hosting users manage their own websites.

Use **Basic** for ordinary HTTP caching without a WordPress plugin. Use
**UltraCache** with the compatible **[UltraCache WordPress plugin](https://github.com/orloxgr/ultracache-dev)** to combine
cached public pages with each visitor's personal fragments on the server.

[Latest release](https://github.com/orloxgr/varnish-for-hestia/releases/latest) ·
[Changelog](CHANGELOG.md) · [Administration](docs/administration.md) ·
[License](LICENSE)

## Requirements

- An existing **Ubuntu amd64** server with HestiaCP and **Nginx → Apache/PHP-FPM**.
  The documented fresh-install platform is **Ubuntu 26.04 with Hestia 1.10.x**;
  fresh package installation uses the official Ubuntu `resolute` repository.
- **Nginx 1.29.3 or newer** for native response-header inheritance.
- Administrator SSH access for installation and updates.
- For the UltraCache profile: an installed, enabled, compatible **UltraCache
  WordPress plugin**, configured for this website's Varnish connection and token.
  Use the matching component versions listed in the
  [release notes](https://github.com/orloxgr/varnish-for-hestia/releases/latest).

The installer installs the signed Varnish package when needed and builds the
addon's native extension against the installed Varnish SDK. An existing unmanaged
Varnish installation requires [explicit adoption](docs/administration.md#adopt-an-existing-native-cache).

## Install

Run these commands separately over SSH, continuing after each succeeds:

```sh
sudo git clone https://github.com/orloxgr/varnish-for-hestia.git /usr/local/src/varnish-for-hestia
```

```sh
sudo python3 /usr/local/src/varnish-for-hestia/tools/install.py --memory-mb 1024
```

```sh
sudo systemctl is-active varnish
```

The example allocates **1 GiB of cache storage shared by all websites**. Choose
a budget appropriate for your server; Varnish also uses RAM outside cache
storage, and PHP, databases and other services need their own RAM.

Open **Hestia → Plugins → Varnish**. The initial default profile is Basic. Choose
the profile for each website and save. Existing accounts and sites are discovered
during installation; newly added ones are picked up by automatic reconciliation.

For WordPress with UltraCache, install and configure the compatible WordPress
plugin first, connect it using the website's Varnish token, then select the
UltraCache profile. Redetect its Varnish capabilities and use its normal cache
clear and Warm operation to populate the application cache.

## Basic vs UltraCache

| | Basic | UltraCache |
| --- | --- | --- |
| Intended use | WordPress without UltraCache and other HTTP applications | WordPress with the compatible UltraCache plugin |
| WordPress plugin required | No | **Yes: UltraCache** |
| Public HTML and HTTP caching | Yes | Yes, with application-approved storage and freshness |
| Cookie policies | Independent Basic choices | Independent UltraCache choices, with application integration |
| Personal content | Delivered by the application; matching private requests bypass shared caching | Public HTML and separately cached personal fragments composed into one response |
| ESI composition | No | Yes, using the application's includes and authenticated fragment endpoints |
| Valid complete HIT without WordPress | Public responses eligible for Basic caching | Public parent and personal fragments when all required objects and owner/lifetime inputs remain valid |

### Basic

Basic is best-effort HTTP caching and works without UltraCache or any other
WordPress plugin. It caches eligible public responses, follows HTTP freshness
and the selected cookie policies, and keeps known administrative, authenticated
and cart/checkout actions out of shared caching.

It does not split a page into personal fragments, regenerate WordPress nonces
or turn private application output into a shared page. A visitor with private
state may therefore reach PHP even when an anonymous visitor receives a HIT.
Basic also supports other HTTP applications, with CMS-specific private routes
where detected.

### UltraCache

**Do not select this profile on a WordPress site without the compatible
UltraCache WordPress plugin installed, enabled and connected.** The profile
depends on the application's cache policy, authenticated publications, fragment
endpoints and invalidation events. Selecting it alone does not add those
features; missing or incompatible integration can cause failed delivery or
incorrect handling of personal content. Use Basic until the integration is ready.

With the application connected, the profile provides:

- **Server-side page composition:** cached public HTML combined with personal
  content such as supported cart, wishlist and nonce fragments. This mode does
  not require a new browser Ajax request to complete the HTML and works without
  JavaScript for supported server-rendered fragments.
- **Personal fragment reuse:** complete, valid cached pages and fragments can
  be delivered without calling WordPress prepare/finalize on every HIT.
  Missing, expired or invalidated objects refill through the application.
- **Visitor isolation:** personal objects retain their actual owner/session,
  cookie inputs, content dependencies and natural expiry. Real provider events
  invalidate the affected objects rather than requiring all application work
  to stop before a valid HIT.
- **Application-aware caching:** the application's explicit storage approval and
  lifetime govern eligible UltraCache output while browser cache headers retain
  their purpose. Original, WebP and AVIF HTML representations remain separate
  where required.
- **Cookie lifecycle integration:** providers create, renew and delete their own
  cookies. A cached page never replays another visitor's personal Set-Cookie
  values, and the proxy does not invent tracking identifiers or grant consent.
- **Optional async cart support:** when explicitly enabled in UltraCache, its
  existing async cart path remains available instead of server-side composition.

These features apply to content and providers supported by the WordPress
integration. Enabling the profile does not automatically make every dynamic
plugin or every private response cacheable.

## What you can manage

### Websites and cache invalidation

Enable or disable caching per website or account, choose profiles, change
website purge tokens and clear caches from Hestia. Administrators also have bulk
controls and a default profile for newly discovered websites. Accounts and
website cache keys remain separate; aliases follow their website settings.

Supported exact PURGE and batch/regex BAN operations let connected applications
invalidate their own cached content. Central and per-site VCL additions provide
further control without editing Hestia's core files.

### Cookie policies

Open **Cookie policies** for central defaults or a website's overrides. Search
cookie names, providers and descriptions; edit rows, add custom cookies, paste
tab-separated rows from a spreadsheet or apply bulk choices. Basic and
UltraCache have independent columns and action filters.

| Action | Effect |
| --- | --- |
| **Shared** (currently **Shared HTML** in the panel) | Share public HTML across the cookie's values while preserving the original cookie for the visitor and application. Personal response-cookie values are not stored for replay. |
| **Vary** (currently **Public variant** in the panel) | Keep separate cached representations for the cookie's values. |
| **Private** | Deliver matching requests through the application without sharing their response bodies. |

Website choices override central choices, which override bundled defaults.
**Why / precedence** explains the effective choice and its evidence. Optional
WordPress policy synchronization applies the active profile's choices to the
compatible application's supported cache engines using the same site token.

**The cookie database is bundled with the addon.** Descriptions and executable
default rules are updated together when you update this plugin. There is no
separate cookie-database download or daily update to schedule. Your central and
website overrides survive updates. Recognition data is attributed to
[Open Cookie Database](https://github.com/jkwakman/Open-Cookie-Database);
recognizing a cookie does not create it or provide consent.

### CMS rules, URLs and representations

CMS detection adds known private routes for WordPress/WooCommerce, Joomla,
Drupal, Magento and PrestaShop. You can refresh detection, exclude retired
installation directories or add custom private path prefixes.

Known campaign parameters such as `utm_*`, `gclid` and `fbclid` are omitted from
an internal lookup URL so tracking links can share a page. The application still
receives the original URL on a MISS. Functional query parameters, language and
cookie variants retain their distinctions. Public search, REST and Ajax GETs
can cache when their actual context and response allow it.

### Server and browser cache settings

Administrators can change the shared cache budget, inspect native cache storage
usage on demand and set the backend first-byte timeout. Changing the cache size
restarts Varnish and empties cached content.

Browser caching has central defaults and per-site overrides, with separate
settings for ordinary static files and declared content-hashed immutable paths.
Files already served directly by Nginx stay on that route.

An optional **aggressive caching** setting uses a chosen server TTL for anonymous
HTML even when generic origin headers would prevent caching. It is off by
default, retains explicit cookie/private-route choices and does not personalize
HTML or embedded tokens. See the [site settings guide](docs/site-settings.md)
before enabling it.

## Update

Download the latest code, then run the installer to apply it:

```sh
sudo git -C /usr/local/src/varnish-for-hestia pull --ff-only
```

```sh
sudo python3 /usr/local/src/varnish-for-hestia/tools/install.py
```

```sh
sudo systemctl is-active varnish
```

Keep these commands separate and continue after success. Pulling the source
alone does not update the running addon. Updates preserve tokens, profile
assignments, local rules, cookie overrides and the saved memory budget. The
installer shows progress and applies the generated VCL and managed routes;
no manual per-domain rebuild is needed. Refresh Hestia after the update.

For UltraCache sites, also follow the matching WordPress plugin's update,
capability-redetection and cache clear/Warm instructions. Release ZIPs and any
version-specific upgrade instructions are available on the
[releases page](https://github.com/orloxgr/varnish-for-hestia/releases).

## Documentation

- [Site settings and cookie-policy details](docs/site-settings.md)
- [Administration, adoption, backup, restore and removal](docs/administration.md)
- [Shared integration contract](shared/CONTRACT.md)
- [Development and testing](docs/testing.md)
- [Release history](CHANGELOG.md)

Licensed under GPL-3.0-or-later. Shared cache-policy/native sources are coordinated
with [Varnish for Webuzo](https://github.com/orloxgr/varnish-for-webuzo); this addon
installs and operates independently on Hestia.

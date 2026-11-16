# 0.16.2 stored PHP page-cache Accept verification

The full Hestia suite passed **151 tests in 185.898 seconds** in the isolated
Ubuntu/Hestia VM with native Varnish. The shared HTTP runner passed **33 cases /
63 profile runs** against Hestia's generated Basic and UltraCache adapters.

The development comparator confirmed byte-identical policy, cases and runner
against Webuzo 0.4.4 (commit `7fa6246`), matching native JSON reports and complete
coverage of all 63 profile runs. The shared contract is also byte-identical.

| File | SHA256 |
| --- | --- |
| `shared/cache-policy.vcl` | `9408d8b5d5b4467d867226de221ce500e85c3672d0c896b75195b2ce77b6a641` |
| `shared/CONTRACT.md` | `8960c3efa06b3a1a9caa3d10d17bd0a8412478f5c98b2ca565fbdd192f486c5b` |
| `tests/shared_policy_cases.json` | `b67e274308b7ad4fc18714fb2e148baa84bdc96ed7f88c762e81764e05b09696` |
| `tests/shared_policy_parity.py` | `92dee05a5b06ec25510aaabc83657eec22b47374a27bfffe40ef56e5942c1c58` |

New native cases verify stored PHP page-cache HIT reuse across compatible
browser Accept headers and codec q=0, a warmed ESI parent reused by two visitors
with separate personal fragments, dynamic STORE retaining raw Accept variation,
and Set-Cookie privacy despite an origin HIT marker. Existing authentication,
cart, host isolation, functional variation and invalidation checks also pass.

These Hestia native cases use deterministic HTTP origins. The separate real
WordPress/UltraCache/Edge check is documented by the Webuzo integration.
Production was not changed; installed lab Varnish, Nginx and Apache service PIDs
were unchanged before and after the full Hestia suite.

# 0.16.1 installer console verification

All **24 targeted Varnish tests passed** in the disposable Ubuntu/Hestia VM:
installer output/argument dispatch, progress, child errors and atomic deployment.
The same run passed 20 Dragonfly, 31 De-Noise and 10 Mass WP Update checks.

The default installer now reports a readable final summary. Explicit `--json`
keeps one complete JSON document on stdout, with progress and technical diagnostics
on stderr. Tests cover slow work, closed streams, failure stages, exit status,
optional terminal color and quiet behavior outside installer reporting. The
Mass WP Update tests publish/reinstall into a disposable directory tree and verify
that the reporter is included in the installed generation. Existing De-Noise
publication/rollback and saved-policy tests also pass. No production installation
was performed. Earlier full VCL verification remains recorded below.

# 0.16.0 shared Webuzo/Hestia policy verification

The Hestia full suite passed **143 tests in 206.169 seconds** on the isolated
Ubuntu 26.04 / Hestia VM with native Varnish 9.1. The same frozen source also
passed the unchanged shared HTTP suite: **29 cases / 56 profile runs**.

The Webuzo 0.4.3 integration passed its **146 tests in 154.027 seconds** and the
same **56 shared profile runs**. An explicit development comparison of both
repositories and their native JSON reports confirmed byte-identical policy,
case and runner files and identical complete passed-result records:

| File | SHA256 |
| --- | --- |
| `shared/cache-policy.vcl` | `7cea910fa4e05a4d874fb01f8ca51c28fe1e56d1af503ce219d0bc8d529edefb` |
| `tests/shared_policy_cases.json` | `38bb8fd00002b6d81aae491072df3eb12bea93fb5ebd130fca4ec2dde11be797` |
| `tests/shared_policy_parity.py` | `92dee05a5b06ec25510aaabc83657eec22b47374a27bfffe40ef56e5942c1c58` |

The shared cases cover original origin URL/Cookie/Accept preservation, tracking
URL and analytics-cookie HITs, consecutive tracking arguments, nested functional
URLs, functional search/ref/language/currency and Cookie variations, consent and
unknown cookies, canonical exact/soft/batch invalidation and host/language/scheme
isolation. They exercise static HTML warmup/browser image capabilities, image
q=0, dynamic/quoted/large Accept headers, absent versus present-empty Accept and
Cookie fields, nonce/private route guards in subdirectories, public query values
containing private-looking paths, response Set-Cookie/surrogate privacy, two
independent private ESI visitors and reusable public ESI fragments. Native header/
workspace allowances are enlarged only in the large-header test, not by the
addon or installer.

Hestia's existing native transport, scope/authentication, state preservation,
parser, rollback, configuration and cache-policy tests also passed. The atomic
publication test confirms that the full shared source is included in installed
code. The comparison and JSON reports are development checks; runtime and
installation do not access another checkout or network policy file. Origins are
deterministic HTTP fixtures. Production and installed VM services were not
changed by these checks.

```sh
python3 -m unittest discover -s tests -v
python3 tests/shared_policy_parity.py --adapter tests/parity_adapter.py --output parity-results.json
```

# 0.15.1 native policy verification

The complete suite passed **143 tests in 178.446 seconds** on the isolated
Ubuntu 26.04 / Hestia lab with native Varnish 9.1. After the final installer
dependency-cleanup change, all **7 installer tests** passed again. All four PHP
panel files passed PHP 8.3 lint. A read-only `apt-get -s install varnish` selected
the official repository candidate without an explicit package version.

Native runtime tests change `uncacheable_ttl`, `default_grace` and `default_keep`
and verify that both presets follow those settings. Public responses retain an
origin TTL of 1800 seconds; uncacheable responses remain separate without forced
grace/keep values. Parallel private fetches and a private-to-public transition
remain covered by the existing hit-for-miss tests.

Public 404/410 responses with origin freshness MISS then HIT. Native 500/503
freshness remains noncacheable unless a central/site rule explicitly sets a
positive TTL; the addon no longer vetoes that rule by status alone. Private
errors remain uncacheable even with an explicit site TTL. Ordinary Set-Cookie
responses preserve public, no-cache or absent Cache-Control and deliver each
visitor's own cookie/body. Private ESI and consumed surrogate privacy remain
protected. The existing two-visitor ESI, async parent, authentication, scoped
purge/BAN, Nginx transport, state preservation and rollback tests passed.

Installer tests verify unpinned APT selection, the matching distro boundary,
no manual library-generation removal, and rejection of an installation plan
that would remove unrelated services. Actual package installation/upgrade was
not performed by this verification; the APT command was a simulation. Production
and the lab's installed addon/service configuration were not changed.

# 0.15.0 shared Basic / UltraCache policy verification

All **137 tests passed** in **174.298 seconds**.

Verified in a separate checkout on the disposable Ubuntu 26.04 / Hestia lab,
using native Varnish 9.1 and PHP 8.3. The production server was not changed and
the lab's installed panel/service configuration was not replaced. Native HTTP
origins are deterministic fixtures; no customer WordPress jobs or orders run.

The native suite verifies both presets with public HTML/CSS, search, REST,
XMLHttpRequest and referral reads; different functional queries remain distinct.
Referral Set-Cookie reaches each visitor without replay from a shared object.
A warmed parent is reused by browser requests with different analytics cookies.

Vary: Cookie tests retain original cookies at the origin, merge only analytics
identifier variants and keep locale/unknown values separate. Delivered Vary
names the real Cookie header. Accept tests retain JSON/XML/image negotiation,
normalize equivalent unquoted whitespace and preserve q=0. A compressed cached
object is served uncompressed to a client that rejects gzip.

Two independent Woo-style sessions receive their own notices and Store API/cart
responses. Ordinary parents cannot borrow the ESI/async approval of another
object. ESI private fragments, authenticated/no-opt-in requests, cold misses,
Set-Cookie, Vary, private/no-store and Surrogate-Control remain covered. Consumed
surrogate privacy and unapproved private parents retain private/no-store delivery
headers for downstream caches. Basic rejects forged private-transport/capability
headers, and both cache diagnostic headers agree on HIT/MISS/PASS and reason.

State tests exercise General/WordPress/WooCommerce conversion to Basic, central
rule scoping/order, application against old applied state, idempotence and token,
ID, cookie and local setting preservation. HTTP contract exact/soft purge and
scoped BAN, tenant isolation, native Nginx routing/headers, atomic rollback and
existing administrator/owner boundaries remain in the suite. All panel PHP
files pass the PHP 8.3 syntax check.

# 0.14.1 installer progress verification

All **124 tests passed** in 204.480 seconds.

The normal installer was exercised on the disposable Hestia 1.10.6 VM. It emitted
immediate timestamped stages on stderr and one intact JSON result on stdout.
Six actual domain proxy regenerations displayed `Domain 1/6` through `Domain 6/6`,
then configuration validation and Nginx worker reload. A separately held native
operation lock produced the wait message and a ten-second heartbeat; installation
completed after the lock was released. Varnish PID and active VCL bytes were
unchanged, with zero site invalidations. Closed diagnostic streams and quiet
panel/API behavior have dedicated regression coverage. No production deployment
was performed during verification.

# 0.14.0 verification

Verified on the disposable Ubuntu 26.04 / Hestia 1.10.6 lab with native
Varnish 9.1 and Nginx 1.31. Production was not accessed or modified.

Run the native suite from a checkout on Linux:

```sh
python3 -m unittest discover -s tests -v
```

All **119 tests passed**, including the existing control, privacy, cookie,
tenant-isolation, cache-sizing and transaction tests and the added async-cart,
hosting-timeout and static-browser-policy regressions.

The async tests verify warmed public parent HITs for two different cart/session
visitors, distinct private cart responses, private cold misses, login and
no-opt-in exclusions, unapproved objects, Set-Cookie, private/no-store and
Vary: Cookie. The General and other profile tests verify query-value separation,
unknown-cookie reuse and public non-HTML caching.

The native Nginx test verifies ordinary and declared immutable asset headers,
ETag revalidation/304, one addon Cache-Control field, retained parent response
headers and the original dynamic fallback for missing files. Native custom
parent Cache-Control directives remain administrator-owned policies; they are
not removed by the addon.

The real Hestia installer and authenticated administrator/owner forms were
also exercised: central browser defaults, domain overrides, later central
changes, return to inheritance, central profile VCL and CSRF rejection. Existing
tokens, site choices, saved timeout and warm Varnish objects survived upgrade.
The Varnish manager did not restart. Browser policy changes retained warm HTML.

The opt-in longer runtime test uses only isolated processes and ephemeral ports:

```sh
sudo python3 tests/timeouts_runtime.py --disposable
```

With the generated Hestia proxy template and product VCL, slow GET and POST each
completed in approximately **65 seconds**, despite deliberately short Varnish
process defaults. POST reached the origin once, a two-second streaming gap
completed, and the following warm GET was a HIT in approximately 1 millisecond.

Apache and PHP still enforce their own native limits. A separate long PHP request
through the lab's real Apache/PHP-FPM stack reached the lab's existing Apache
`Timeout 30`; its error log identified the FastCGI response timeout. This was not
a Varnish timeout. The addon does not silently change Apache/PHP execution policy.

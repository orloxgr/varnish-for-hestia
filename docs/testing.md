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

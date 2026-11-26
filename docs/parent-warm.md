# Authenticated public-parent and guest warming

Hestia 0.24.16 shares its native/VCL implementation with Varnish for Webuzo
0.13.25. A compatible WordPress UltraCache warmer, starting with
3.13.13-dev.1391, negotiates the public-only delivery capability before using it.
Clients without the opt-in retain the original v1 signed message and normal
personal parent delivery. Basic is unchanged.

## Behavior

The existing authenticated `parent-v1` request can explicitly select
`public-parent-only` delivery. The selection is part of the signed canonical
v2 message; it cannot be added, removed or changed without invalidating its
authentication. See the exact [Warm protocol](WARM-PROTOCOL.md).

On a fresh public parent HIT, public-only Warm performs no origin or private
composition work. On a cold request with the supported source projection, the
same owner validates the real public source, executes the application's real
anonymous guest compilation, and stores both as ordinary native cache objects
through the existing snapshot backend. Each object retains its own source
binding, actual context, expiry and invalidation rules. A declined anonymous
compilation may still populate the verified parent without claiming a guest fill.

ESI processing is disabled only for the opted-in Warm response. The stored
parent retains ESI capability; subsequent ordinary visitors still receive
normal private fragments and cookie delivery. Plain parents and ESI comments
retain their exact public bytes in the Warm response.

A completed public-only Warm reports `X-UltraCache-Warm-Delivery:
public-parent-only`, personal delivery `not-executed` and private cache status
`NOT-APPLICABLE`. `X-UltraCache-Warm-Guest: populated` additionally reports a
genuine COMPLETE guest insertion by this same owner. It is absent when no such
insertion occurred. The warmer must still verify a fresh real parent HIT and
an ordinary guest GET/HIT with complete HTML. These observations do not claim
that personal fragments were warmed.

Existing Cookie choices, raw Accept context, source validation, owner isolation
and ordinary visitor behavior remain effective. No new endpoint, queue, setting
or cookie exception is introduced.

## Installation

Use the normal addon update and installer in the [README](../README.md). The
installer builds the matching native module and activates generated VCL. Do not
patch VCL manually or deactivate the addon to update it. A compatible WordPress
warmer negotiates the new capability; older v1 clients retain their previous flow.

## Qualification boundary

Native adapter qualification uses Hestia's actual direct-Apache VCL renderer and
mock HTTP application producers on Varnish 9.1. It is separate from paired
WordPress/browser acceptance and from a Hestia production installation. Passing
functional checks does not establish the separate 5–15-second full Warm target.

The candidate passed 20 distinct native methods with no final skips. Both Basic
and UltraCache generated VCL compiled. Coverage includes four paired/protocol
methods, twelve Warm authentication/context methods, ordinary projected guest
fill, normal public-source handling and two full private reuse methods. Native
build identity and library hash match the qualified Webuzo candidate. Installed
Lab module files and services were unchanged.

Paired WordPress dev.1391 and Webuzo 0.13.25 application acceptance was reported
successful: all ten real contexts verified their parent bodies, observed genuine
guest population and completed refill. Two independent cookie-free browsers
received complete HTML HITs with matching bodies, empty carts and no raw ESI,
component or image failures. This was not a Hestia production installation.

The reported full Warm took 89.734 seconds, improved from the previous
106.6-second candidate and 123.3-second baseline. The 5–15-second target remains
unmet; functional acceptance is not completion of that performance goal.

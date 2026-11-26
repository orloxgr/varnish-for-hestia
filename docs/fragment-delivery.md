# Fragment-only transport: Hestia integration qualification

This development change integrates the common implementation from
[Webuzo 1e18268e](https://github.com/orloxgr/varnish-for-webuzo/commit/1e18268e5c521c6283a51c95571332f83558d992).
The exact request, producer and browser contracts are in
[the shared protocol](../shared/FRAGMENT-DELIVERY.md).

Hestia starts the operation only after its actual site/profile dispatch and
enabled-site check, before ordinary document cookie/public selection. Installation
capabilities register the route and fragment caching flag through the existing
authenticated control operation. Browser headers cannot create that registration.

Private batches use the existing continuation, request-owned virtual source,
authority registry and native individual-object namespace. Public fragments keep
their signed canonical GET URLs. Neither the batch route nor ESI/Ajax delivery
becomes an individual object-key dimension. Caching OFF bypasses retained
fragments; parent HTML caching and Shared/Vary/Private decisions remain independent.
Basic gains no ESI or WordPress dependency.

## Executed checks

Two disposable Lab runs executed **47 distinct methods, with zero failures,
errors or skips**, using the actual Hestia direct-Apache VCL renderer and native
Varnish 9.1. Both Basic and UltraCache generated programs compiled.

- Nine portable C batch-codec methods and fifteen legacy envelope methods.
- Five native batch methods: request-local output and current cookies, seven
  individual objects across batches, bidirectional ESI/Ajax reuse, caching OFF
  with a hot public fragment and unaffected parent, and a real authority writer
  retiring a rendered claim before storage/delivery.
- Four existing private-TTL methods and seven application-independent profile
  compatibility methods.
- One Hestia subdirectory/ingress method, one native-source artifact identity
  method and five engine build-receipt methods. The ingress check covers actual
  private-cookie forwarding, uncached batch JSON, another installation path,
  unnegotiated operation, Basic and a disabled site.

Two VCL module checks and four backend credential/source-render checks also passed
locally. These are separate from native execution. A Windows-only deployment test
discovery skipped four Linux root tests and is not counted as qualification.

The native module build signature was
`06b342bbcb6134699b4594ab299607a959b5d6f62b91bc13e87472222f71473a`;
DSO SHA256 was
`49806d5a86943de44cbaccdf79d68c32ec43f161cb68269f1c65298390b8d62e`.
Both independent runs produced the same receipts. The installed module directory
was verified unchanged; no installed service was reloaded.

A follow-up from [Webuzo b0f82259](https://github.com/orloxgr/varnish-for-webuzo/commit/b0f82259f28ec5678d73faa94fef924ed085cea5)
fixes capability discovery before route registration. An empty route must not be
treated as an accepted declaration. A third disposable native run passed the new
initial-discovery-to-registration method and repeated the Hestia scoped-ingress
method, with no skips or failures and both profiles compiled. This adds one
distinct method to the 47 above. The shared change is VCL-only; C/build inputs
and native module identity are unchanged. Installed modules/services remain
untouched.

The subsequent [Webuzo 721c0dcd](https://github.com/orloxgr/varnish-for-webuzo/commit/721c0dcd6ebb35e14bff69e8415e9419b66f0683)
delta keeps the existing parent-delivery gate separate from valid fragment
participation. A complete fragment declaration retains the same metadata and
authority owner with parent delivery OFF or fragment storage OFF. Partial
declarations fail before metadata changes. Full teardown omits the fragment
declaration and retains normal authority revocation.

On this delta, all seven native batch methods plus the Hestia scoped-ingress
method passed in a fourth disposable run, with zero failures/errors/skips and
both profiles compiled. The new control scenario proves parent OFF with a
fragment HIT and unchanged authority revisions/remaining expiry, storage OFF
with fresh request-local delivery, and complete teardown. It adds one distinct
method to the prior checks; earlier results retain their original source scope.
The matching native build signature is
`ab861ead2317b1187187542f2b39b74b3d4c31b609dee4c4d7cdd2c5e76bfcdb`;
DSO SHA256 is
`c1ba6fe1acd2ee9c094da156cbcddd2d62b1b48497c22aa1640c5dea27f9ddea`,
identical to the canonical Webuzo build. Installed modules/services were unchanged.

The prerelease stateless extension from
[Webuzo 6dc41a6c](https://github.com/orloxgr/varnish-for-webuzo/commit/6dc41a6c52d931c2fdd447d3c8fb7c838f3f9d23)
permits only an explicit authenticated schema2 `cache.identityState: "anonymous"`
claim with empty cache tags and exact per-URL empty authority. The complete
current scope/epoch/incarnation/revision/policy tuple remains required.
Missing identity state does not imply anonymous; personal claims still require
their complete nonempty dependency list. The legacy parent/envelope/reuse
metadata parsers reject the new field. No object key, store, lifetime or cookie
policy changes accompany this extension.

On that exact source, a fifth disposable Hestia run passed **59 methods** with
zero failures/errors/skips and both profiles compiled: eight native batch plus
one Hestia ingress method, ten portable batch-codec, fifteen legacy envelope,
twenty public-selection parser and five build-receipt methods. The focused native
test proves stateless first-MISS-to-HIT reuse without another render and rejection
of a hot claim after actual reuse-policy namespace revocation. These are mock
producer checks, not evidence of the real WooCommerce stateless claim lifecycle.
Native build signature:
`b93c7db7b4e2a5a8094c3fa8f541dc4129f9dd3fefb7dc83ce3eaa99d3af71d2`;
DSO SHA256:
`a7146f614a213490561bd822689f42cc8c3489dba8f525ef04dc6798d4642b89`.
Both match the canonical Webuzo normal build. Installed modules/services were
unchanged; no live deployment or release was performed.

Every one of the twenty shared delta files was checked against its base hash
before application, then against the immutable canonical target. The product
source comparison also passes. Historical test-fixture comparison is separate:
some older expectations differ between adapters, so `--source-only` does not claim
that those historical fixture files are identical. The retired recognition
downloader is not part of the common runtime comparison.

## Remaining acceptance and upgrade boundary

### Development candidate 0.24.18-dev.1

The installable development ZIP contains the committed Hestia sources and
declares `0.24.18-dev.1` in `addon.json`, which is also the installer/panel version
source. It is distinct from the existing 0.24.17 release. No GitHub release/tag
or live Hestia installation accompanies this candidate. Shared native/VCL inputs
remain identical to the qualified Webuzo `6dc41a6c` implementation above.

For an existing Git source installation, use the normal pull/installer commands
below. The installer reconciles the enabled site routes and generated policy;
Hestia needs no Webuzo-style Refresh or separate domain rebuild. Capability
discovery occurs through the matching WordPress integration's normal detection.
Use the coordinated WordPress development candidate for the new fragment mode;
this document does not designate an older WordPress version as compatible with
the new controls.

These native tests use trusted mock HTTP application producers. They do not prove
actual WordPress session/provider ownership, standalone SQL storage, browser
initialization, consent or component behavior. Those checks belong to the matching
WordPress implementation and coordinated acceptance in
[UltraCache issue 1084](https://github.com/orloxgr/ultracache-dev/issues/1084).
No live Hestia installation, new addon release or installation-ready companion
version is claimed by this document.

When coordinated releases are qualified, an existing Hestia source installation
uses the normal upgrade:

```sh
sudo git -C /usr/local/src/varnish-for-hestia pull --ff-only
sudo python3 /usr/local/src/varnish-for-hestia/tools/install.py
```

The installer builds the matching native module and applies generated VCL while
preserving credentials and site choices. No manual VCL edit or separate domain
rebuild is part of this integration. Use the compatible WordPress release and
its normal capability discovery; the new mode is not inferred from an addon
version or an unverified header.

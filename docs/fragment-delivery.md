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

Every one of the twenty shared delta files was checked against its base hash
before application, then against the immutable canonical target. The product
source comparison also passes. Historical test-fixture comparison is separate:
some older expectations differ between adapters, so `--source-only` does not claim
that those historical fixture files are identical. The retired recognition
downloader is not part of the common runtime comparison.

## Remaining acceptance and upgrade boundary

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

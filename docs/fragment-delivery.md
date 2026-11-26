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

### Development candidate 0.24.18-dev.5

The six shared files match
[Webuzo 25f5c613](https://github.com/orloxgr/varnish-for-webuzo/commit/25f5c613ac5f14ac804b8265ecf0aec196908be7)
after verifying every base and target hash. Explicit anonymous schema2 identity
can retain actual product/content dependencies without becoming owner-bound.
Nonempty cache tags require a nonempty current per-URL content authority closure;
empty tags still require an empty closure. The full scope, policy, revision,
generation and writer validation remains required before native fill and final
release. Personal claims and legacy schema1 are unchanged.

The authenticated registered-route capability reply adds
`X-UltraCache-VCL-Fragment-Anonymous-Authority: 1`. An unregistered route or full
teardown omits it. Applications must observe this scoped capability before
emitting anonymous content-tagged claims; older native versions omit the field.
No transport version, native ABI field, cookie policy, object key/store or TTL
change accompanies the refinement. Basic still has no ESI or application dependency.

A disposable Hestia native run passed **37 methods with zero failures, errors or
skips**, and both profiles compiled: four focused native batch methods, one
Hestia scoped-ingress method, eleven portable batch-codec methods, fifteen legacy
envelope methods and six build/source-identity checks. The content-tag scenario
fills and reuses an anonymous body, begins a real native authority mutation while
that body remains a storage HIT, refuses browser release with state-conflict,
then commits and publishes a fresh generation before refill/HIT. Capability
registration, storage OFF, read-only scope and full teardown also pass.

Normal native build signature:
`996a9475cf85d85ea8497d9dd59afc91f0e3c666e5529e7540099a7e9c3b965c`;
Lab DSO SHA256:
`1d6c479339e08b4b5b82d7fb44c1384fa5f502ab05a08173bd5f017a13b727d9`.
Both match the canonical Webuzo normal build. The installed Lab module directory
was hash-verified unchanged; no installed service was reloaded.

This is native trusted-mock-producer evidence. Actual WordPress product database
editing, the corresponding application content-tag normalization and paired
browser acceptance remain separate, with the matching WordPress development
identity pending. Earlier dev.4 WordPress receipts retain their exact versions
and scopes. The dev.5 archive is distinct; prior ZIPs remain unchanged. No Hestia
live installation, manual Refresh, tag or public release was performed.

### Development candidate 0.24.18-dev.4

The exact shared delta from
[Webuzo ee5c0bc3](https://github.com/orloxgr/varnish-for-webuzo/commit/ee5c0bc343775754393e54c1264eebafc31f9f60)
adds only the read-only `cacheScope` success-result metadata and its contract.
It reports anonymous/private after completed native dispatch, positive object
lifetime and final authority validation, or none for request-local output.
Caching OFF removes the claim and yields none. Failed/retired items have neither
body nor cacheScope. It is not a producer input, permission, identity assertion
or new cache grant; no key, lifetime, policy, VCL or ABI change accompanies it.

A disposable Hestia run passed exactly two focused native methods plus 25
portable parser/wire methods, with zero failures/errors/skips and both profiles
compiled. Actual private lookups returned404 before dispatch and200 after it for
both anonymous/private objects; storage OFF returned404 and reported none.
A real writer retired the other tested result without exposing body/metadata.
Native build signature:
`fff50dd5831b99d888e91d15a82cc3688e932f0c7b250675b2a125f2c15d4fe4`;
Lab DSO SHA256:
`8f981f13ee9ca626dbfd0a41872ba7545e3672f1f045191707e04709ea33afc5`.
Both match the canonical Webuzo standard build. Installed modules/services
remain unchanged.

The candidate declares `0.24.18-dev.4` through the existing addon metadata.
WordPress dev.1412 remains the last identified companion baseline; the matched
WordPress increment consuming this evidence for Warm is still pending, so no
version or completed Warm behavior is inferred here. Use the normal installer
commands below during coordinated installation. No Hestia deployment, tag or
public release accompanies this candidate; prior ZIP bytes remain unchanged.

### Development candidate 0.24.18-dev.3

The exact shared correction from
[Webuzo 5fb52940](https://github.com/orloxgr/varnish-for-webuzo/commit/5fb529406d1d90e99653f11730fe050febc5d87d)
keeps canonical fragment Ajax outside full-document public selection. Ordinary
site ingress, route/cookie policy, origin signed-descriptor/scope validation and
HTTP cache decisions remain in force. No C, ABI, namespace, key, TTL, policy or
limit change is involved; the native signature/DSO remain those of dev.2.

A focused Hestia fixture reproduced PASS/PASS on immutable dev.2 and passed
MISS/HIT after the correction. It also verifies no document prepare, exact purge
without retiring a sibling or parent, and repeated origin403 for invalid/private
requests. That method, hot-public caching-OFF and Hestia scoped ingress passed
in one disposable run: three methods, zero skips/errors/failures, both profiles
compiled. The Webuzo-specific global-gateway assertion is not claimed as a
Hestia gateway check. Installed modules/services were unchanged.

The installable candidate declares `0.24.18-dev.3` through the same addon metadata
used by installer/panel status. Its coordinated WordPress companion is
3.13.13-dev.1412, source `68569de6b0493ecbba55cc95ea44b5c00500cc97`.
Normal Hestia update commands below remain unchanged. No live Hestia deployment,
tag or public release accompanies this candidate; prior archives are preserved.

### Development candidate 0.24.18-dev.2

This candidate adds only the two-file shared correction from
[Webuzo d0171d0c](https://github.com/orloxgr/varnish-for-webuzo/commit/d0171d0ce917aad4913078b683e19e7650665db8)
to the qualified development runtime. During a native-owned finalizer return,
the temporary metadata request deliberately lacks Cookie. The request may reuse
its original classification only with the existing native phase/site/host/URI/
restart proof and the same captured original input. Ordinary missing, changed,
duplicate or forged cookie input is not an authorization to reuse.

The exact synthetic fixture reproduced 503 and `regsub: Out of workspace` against
the immutable dev.1 source at native default workspace. With the correction,
fourteen methods passed without skips/failures/errors, and both profiles compiled:
the same thirteen-placement/1678-byte-Cookie finalizer fixture, three retained/
forged/changed-cookie workspace methods, all eight fragment batch methods, one
normal complete-reuse method and the Hestia scoped-ingress method. The fixture
asserts one classification per original request and distinct-owner reuse. No
workspace or header limit was raised. Webuzo global-gateway fixtures are specific
to that adapter and are not presented as Hestia gateway acceptance.

The matching native build signature is
`648c5d27614dbc45e324cd2e01a5f70f52700580d174b19b8d340d92003e737a`;
Lab DSO SHA256 is
`115905c320c8581ad3488b42571b2df6b10d1cd9f5d61a23e7aacbbe51c3dffa`.
Installed Lab modules/services remain unchanged. The installable ZIP declares
`0.24.18-dev.2` through the same addon metadata consumed by installer/panel status.
Use the normal update commands below with matching WordPress development
candidate 3.13.13-dev.1408. No Hestia live deployment, tag or public release is
performed; dev.1 archive bytes remain unchanged.

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

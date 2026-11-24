# Projected Variant first-lookup identity

Tracked by https://github.com/orloxgr/ultracache-dev/issues/1023 under #1006.

The shared native change and five-case fixture are byte-identical to Webuzo.
Before the initial registered/projected lookup, vmod_selection_begin now uses
the existing delivery_selection_projection serializer and updates the existing
request-owned classification snapshot. The lookup key and projected publication
therefore use the same ordering and duplicate semantics. Raw Cookie, policy
choices, Basic and nonprojected/unregistered behavior remain unchanged.

The old Hestia renderer/module reproduced three failures in five new cases,
including an apparent final HIT that had executed three additional application
calls. The changed Hestia run passed 12 methods, with no failures/skips. These
covered all five new cases plus existing native public/private source handling
and a nonprojected control. Separate Webuzo qualification passed 15.

Both independently compiled modules had signature
9b2e49a54e84ffc0556d828bfe94924faebbf29e8faa17131d4e590edd04b168
and SHA256 d2e7170f1c66b86e76338338564457857fc05fc35a91b719772eebbc951ccc3e.

The application was an explicit transport mock. This proves the native identity
fix, not complete WordPress/provider/browser or Enterprise behavior. No installed
services/modules, live sites, release tags or ZIPs were changed for these tests.

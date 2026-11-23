# Covered continuation header/workspace repair

The shared native change is copied exactly from Webuzo commit
`770309a7d8e95dabdcba6c53a5a200027f8de817`. It fixes two separate finite-resource
peaks without changing cookie policy, protocol or server limits:

- An owned typed prepare does not carry the four backend storage-only Vary
  scratch headers. The owning request/continuation and actual recovery/ordinary
  origin representation retain their inputs.
- Restoring an already identical single original header or URL does not allocate
  another copy in the client workspace. Changed/duplicate fields still take
  normal restoration; absent and empty are distinct.

The matching active-coverage fixture uses synthetic 2315-byte consent cookies,
real native context verification and a mock application. Its ordinary POST case
checks the exact original URL/query, Cookie, Authorization, content type and
form body. Hestia retains its own proxy fixture parameters and startup behavior;
only optional request-body capture is added for the new preservation case.

The source port alone is not runtime qualification. Hestia matching-module
native tests and real WordPress/browser acceptance remain required. No live
Hestia deployment, release, limit increase or policy change is claimed here.

The follow-on shared delta fromWebuzo9c120736c98b325e6e23ea20cda047bcf0185b89
also covers the larger6144-byte active-coverage fixture. It retains original
per-rule normalization, accumulates ordered Variant groups on the owning task,
avoids duplicate header/getter copies and extracts diagnostic names without
materializing another large value header. Existing phase/site/host/URL and exact
Cookie checks still own continuation reuse. See the common header-budget note
for the separate normal/disabled-engine differential tests and qualification
limits. The older770309a result does not qualify this follow-on source.

# Application storage approval and browser cache headers

Application policy integration checkpoint #1022 under the coordinated #1006 work.
See the [public functional acceptance summary](functional-acceptance.md).

The shared VCL application-policy increment is identical to Webuzo. An approved
UltraCache HTML response uses its existing cacheable/TTL contract for storage
while preserving browser Cache-Control/Pragma/Expires. Upstream Age reduces its
remaining freshness. Basic, explicit privacy and signed fragment owners retain
their existing behavior; no Aggressive switch or new protocol is needed.

Five identical shared HTTP cases and two existing Hestia privacy/ESI cases
passed with the pinned native module. The first shared attempt failed because
tests/parity_adapter.py ignored SCP_TEST_COOKIE_MODULE and imported an older
installed module. It now uses the fixture variable already supported by the
other native tests. The failed first receipt is retained, and the separate
follow-up passed. No installed service/module was changed for testing.

The matching WordPress normal-generator/WP-FPM check passed three browser-header
roundtrips, including a real native PHP session, and restored exact original Lab
files afterward. These focused results do not replace full-package installation,
browser and private-cache lifecycle qualification. No release or deployment is
claimed by this increment.

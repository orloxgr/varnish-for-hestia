# Raw Warm source routing — 0.23.8

The behavior patch a753f54 applies the exact shared routing/collector-cookie
correction published in Webuzo e4594a0 (0.12.11). It precedes guest lookup only
for the existing complete UltraCache raw Warm GET shape. This is routing, not
authentication: the origin still checks its runtime MAC and registry capture.
No change is made to Basic or ordinary browser cache-control behavior.

## Actual native qualification

An exact Git archive of a753f54 was extracted on the isolated Linux Varnish
Lab. The module was compiled from that Hestia source against the installed
engine into an owned test directory; no system module was replaced.

- 24 tests passed in 220.745 seconds: request revalidation/raw capture, guest
  publication and signed warm projections. Both hot guest and ordinary cache
  objects, valid/invalid credential shapes, preserved raw cookies, all three
  representations and Basic behavior were exercised through real Varnish.
- Module SHA256: 5640067773db6d1774468567a20621fb1cd757f3801ddca4ebe8fd197b4e38db.
- 25 Linux installer/deployment/output tests passed. Their filesystem targets
  were temporary Hestia directory trees; PHP syntax lint in the small deployment
  unit fixtures was mocked. These are installer contract tests, not a live panel
  installation or proof of WordPress behavior.

## Application evidence and its scope

The identical shared correction was installed on authorized live Princefrog
through Webuzo0.12.11's canonical package lifecycle and normal Refresh sites.
The previously failing hot Warm succeeded, as did normal targeted Clear/Warm.
An additional real normal capability redetection was necessary because the
WordPress installation retained an older working-private proof with missing
continuation declarations; after redetection the product also warmed normally.

Four independent fresh browser contexts then received complete guest HITs with
real empty cart regions: home44/43ms TTFB and product48/47ms. Four separate
ordinary no-cookie HTTP requests returned identical public bodies. Exact native
VSL roots proved zero backend/PHP calls and zero ESI children for those four
HTML deliveries; native response time was approximately1ms.

This is actual WordPress evidence on Webuzo, not an Hestia WordPress or live
Hestia deployment claim. The larger private-fragment goal, its current Hestia
port, repeated private-browser zero-PHP acceptance and automatic handling of old
capability proofs remain separately open in UltraCache#1006/#1019.

## Updating

Extract the release source ZIP and use its normal installer:

```sh
sudo python3 /path/to/varnish-for-hestia/tools/install.py
```

Use the actual extracted source path. Omit memory options to retain the saved
budget. The normal installer reconciles the active VCL and preserves existing
site settings and tokens; copying files alone does not activate a VCL update.
No live Hestia update was performed for this release qualification.

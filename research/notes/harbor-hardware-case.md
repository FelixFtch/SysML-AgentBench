# Concrete harbor inspection case

Verified 2026-09-22. This is a proposed civilian demonstration, not an identified RTX product or approved hardware design. The page's existing maritime SysML model remains a synthetic functional model; the physical equipment references below have not been bound to a validated BOM.

## Mission and physical mapping

A crewed harbor patrol boat observes navigation buoy H-07 and quay structures. Two camera channels feed an onboard edge computer; originals are recorded locally, while an explicitly permitted preview is shared with a shore relay and then a second patrol vessel. Existing payloadAlpha / payloadBeta can be interpreted as visible / thermal streams, but their shared camera housing, wiring, power modes and product-level interfaces require additional model work.

## Verified public references

| Reference | Facts used | Primary source |
| --- | --- | --- |
| FLIR M364C | Visible up to 1920×1080 at 30 fps; thermal detector 640×512; H.264 main/substreams; 12–24 VDC; 41 W nominal, 56 W with heaters; thermal refresh variants differ | https://marine.flir.com/en-us/marine-cameras/fixed-mount/flir-m364c |
| reComputer Rugged J4012 | Ethernet; included 128 GB NVMe; 19–48 VDC; typical 25 W. Its documented cooling conditions and software readiness need checking | https://wiki.seeedstudio.com/ai_robotics_recomputer_rugged_j40_getting_started/ |
| Teltonika RUT956 | LTE / Ethernet; 9–30 VDC; IP30 equipment needing a dry protected location. Its passive PoE input is not a camera power source | https://teltonika-networks.com/product/rut956/ and https://wiki.teltonika-networks.com/view/RUT956_Powering_Options |

The camera and computer nominal/typical planning subtotal is 41 + 25 = 66 W, or 56 + 25 = 81 W with the camera heater figure, before radio and supply losses. This flags a conflict with the synthetic model's 60 W limit; it is not a measured peak-power calculation. The synthetic candidate A's 54 W result cannot validate these products.

The ordinary M364C integration article discusses NTP and pan/tilt/zoom metadata: https://marine.flir.com/en-us/support/learning/multispectral-marine-cameras-for-usv-applications . Do not infer a supported target-class/bounding-box/temperature JSON API from that. The separately named M364C-USV model's per-frame SEI claims must not be silently applied to the ordinary M364C.

## Executed specimen vs physical concept

The local replay generates two clearly labeled procedural illustrations, encodes actual JPEGs, validates a small explicit envelope, normalizes fixed timestamps, computes SHA-256, copies and verifies memory buffers, builds a resized preview, and delivers cloned byte packets through browser MessageChannels. The visual subject H-07 is manually assigned; no detector, temperature inference or real camera driver runs.

The replay's preview JPEG and message transport are inspectable examples, not H.264/P2 throughput, RF, SSD endurance, or hardware integration evidence. Actual artifacts are retained under mvp/verification/harbor-replay/ after downloading from the browser. A model-provider connection is not required for this deterministic visualization.

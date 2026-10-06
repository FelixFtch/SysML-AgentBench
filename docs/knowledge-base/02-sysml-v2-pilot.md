# 2. Working with the official SysML v2 Pilot 0.62

## Setup and what a PASS means

- Pilot 0.62.0 (release 2026-08), the Jupyter kernel jar with Java 21, and the standard library from `Systems-Modeling/SysML-v2-Release` at commit `fb97b754` (94 library files); all pinned and hashed in `mvp/toolchain/` and `bench/FREEZE.md`.
- Command: `python3 mvp/toolchain/validate.py --package <Package> --output <folder> <file.sysml> [more files]`. It prints JSON with `status` (PASS or FAIL), every diagnostic with severity, message, file, line and column, and the official model export.
- PASS means parsing, linking and the Pilot's static validation passed. It says nothing about engineering feasibility; budgets and traceability are separate checks on the parsed numbers.
- The adapter compiles once into `mvp/toolchain/build/` under a lock. Concurrent sandboxes each need a private copy of that folder (decision 026).

## What models wrote that the Pilot rejects

Every message below is the Pilot's own text, seen in this project's runs or reproduced with a probe.

| Written | Pilot message | Accepted form |
|---|---|---|
| `import ScalarValues::*;` inside a package | `mismatched input 'import' expecting '}'` | `private import ScalarValues::*;` (or `public import`) |
| `attribute powerW : Real;` without importing ScalarValues | `Couldn't resolve reference to Type 'Real'.` | `private import ScalarValues::*;` as the first line inside the package |
| `connection c { end usv.camera.imagery; end usv.processor.imageryIn; }` | `no viable alternative at input '.'` | `connect usv.camera.imagery to usv.processor.imageryIn;` |
| `alias drawW for OptronicsKit::powerDrawW;` (a feature named without its owner) | `Couldn't resolve reference to Element 'OptronicsKit::powerDrawW'.` | `alias drawW for OptronicsKit::EoCameraUnit::powerDrawW;` |
| `allocate UavSensorSpec::uav::searchRadar to RadarVendor::payload::radar;` | `Must be an accessible feature (use dot notation for nesting)`, but only when the source models are validated before the package (see below) | `allocate UavSensorSpec::uav.searchRadar to RadarVendor::payload.radar;` |
| `allocate UavSensorSpec.uav.searchRadar to RadarVendor.payload.radar;` | `Couldn't resolve reference to Feature 'UavSensorSpec'.` (one message per segment) | as above: `::` up to the usage, dots inside it |

Two conventions settle most of these: an import inside a package needs a visibility keyword, and a path uses `::` through packages and definitions but `.` from one usage to a usage nested in it. Alias targets name definitions and their features, so they use `::` throughout.

A value can also parse and still break a check: when a repair rewrote `attribute fusionLatencyS : Real = 2.0;` as `ISQ::TimeValue = 2.0 [SI::s]`, the model stayed legal but the kept value was no longer read as the plain Real the task required (decision 022, trial on qwen3.8-max).

## Quirks to know

- **The verdict can depend on file order.** The adapter loads all files, resolves references, then validates the files one by one in the order given, and some checks read state computed while validating an earlier file. The `::` nesting error above is reported when the sources come first and missed when the package comes first. Always validate a multi-file package with its sources first and the package last, as the scorer does; `./validate` in the agent sandbox enforces that order. `bench/check_validator_order.py` re-validates every graded alignment answer in both orders (decision 026).
- **Unnamed connections have no name in the export.** Retrieval cards for them are made as `Owner::connect[a → b]`, so "how many connections" questions can be answered from retrieved context (decision 023).
- **Large examples can time out.** Building the retrieval library, 20 of the 21 official example folders parsed; the Vehicle Example timed out.

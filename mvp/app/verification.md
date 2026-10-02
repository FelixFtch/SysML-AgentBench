# Workbench acceptance record

Verified on 2026-09-22 using the running localhost service, the actual official SysML toolchain, and Chrome. No mocked engine was used for the acceptance runs below.

## Application boundary checks

`python3 -m unittest discover -s mvp/tests -p 'test_app*.py' -v` passed all **9 tests**. The original eight checks remain, with a ninth for whitelisted reference dispatch. These unit tests deliberately use mocks only to test the API boundary.

## Six actual HTTP engineering runs

`python3 mvp/tests/test_app_acceptance.py` completed all six cases. Each passed official static SysML validation. The table reports the actual independent engineering checks; hardware/mission-quality verification remains UNKNOWN in every case.

| Request | Storage (GB) | Uplink (Mbit/s) | Power (W) | Overall | Engine run |
| --- | --- | --- | --- | --- | --- |
| baseline | 21.6 / 51.2 · PASS | 7.2 / 8.0 · PASS | 44.0 / 60.0 · PASS | UNKNOWN | `20260922T072858-5e5ea9c0` |
| candidate_a; P2 approved | 64.8 / 102.4 · PASS | 2.4 / 8.0 · PASS | 54.0 / 60.0 · PASS | UNKNOWN | `20260922T072908-7354fceb` |
| candidate_b; P2 approved | 64.8 / 102.4 · PASS | 2.4 / 8.0 · PASS | 68.0 / 60.0 · FAIL | FAIL | `20260922T072920-ef623492` |
| candidate_a; P2 approved; 30 Mbit/s | 108.0 / 102.4 · FAIL | 2.4 / 8.0 · PASS | 54.0 / 60.0 · PASS | FAIL | `20260922T072931-8ce2b7bd` |
| candidate_a; P2 not approved | 64.8 / 102.4 · PASS | 21.6 / 8.0 · FAIL | 54.0 / 60.0 · PASS | FAIL | `20260922T072942-131bee1e` |
| degraded_link; P2 approved | 64.8 / 102.4 · PASS | 2.4 / 1.5 · FAIL | 54.0 / 60.0 · PASS | FAIL | `20260922T072953-0780fe2b` |

All six reopened HTTP records matched their saved JSON exactly. Each ZIP contained **40 files in total**, comprising the complete run directory plus `workbench-record.json`: the file inventory was compared with the actual run directory, and every source snapshot SHA-256 was verified. The source-file read endpoint was also exercised. Numeric details and workbench record IDs are in `verification-results.json`.

## Public-source imports

`python3 mvp/tests/test_app_references.py` completed both actual imports. These are separate public examples; synthetic marine budgets are NOT_APPLICABLE. No physical verification or engineering acceptance is inferred from parser success.

| Reference | Official parser | Named elements | Exported elements | ZIP files | Acceptance | Engine run |
| --- | --- | --- | --- | --- | --- | --- |
| sysml-official-vehicle | PASS | 30 | 501 | 18 | UNKNOWN | `20260922T073335-6f397158` |
| nasa-cfe | PASS | 14 | 273 | 23 | UNKNOWN | `20260922T073343-5f519a28` |

The official vehicle button was also exercised through Chrome, visibly entering the running state and returning parser PASS with engineering status UNKNOWN. Both reference records reopened unchanged. Every source-file hash and complete ZIP inventory matched. The selected-run file inventory also included public-data reference texts. Full evidence is in `reference-verification-results.json`.

## Browser and persistence checks

- The final English candidate A view was visually inspected in a real Chrome screenshot; checks show separate parser PASS, execution COMPLETED and engineering UNKNOWN.
- Chrome displayed all four views—checks, model, sources and raw record—with **zero Chinese characters in visible text**. Application UI strings, application errors and this documentation are English.
- The approved candidate A displayed 83 named parsed elements, 17 part definitions/usages and 9 actual connections. Filtering `recordingConnection` and selecting it showed the official `relatedFeature` chain from `processor.rawToRecorder` to `recorder.rawInput`.
- Selecting the saved `sources/requirements.json` displayed its 4,870-character English snapshot. Source views use the selected run rather than silently showing another run’s files.
- Candidate A was reopened after a server restart. Its parser PASS, overall UNKNOWN, model, decisions and evidence remained available. The P2 checkbox still defaults to false for the next run; the selected result separately identifies its recorded approval.
- A real UI request to the agent endpoint returned an explicit model-not-connected error. No LLM execution is claimed: a provider URL/model and any required credentials still need operator configuration.
- Earlier development records with Chinese diagnostics were preserved under `research/mvp-development-records/` and removed from the formal UI history, without rewriting their evidence.

## User entry point

The service is left running at **http://127.0.0.1:8765**. Open the approved candidate A result at:

http://127.0.0.1:8765/?run=20260922T074240-bad9405f87

Start it again from the repository root with `python3 -m mvp.app` if the local process stops. The actual workbench and source view remain available; engineering acceptance is intentionally not upgraded from UNKNOWN.

## Targeted regression after checker review

After the engine strengthened upload-policy equality, actual connection endpoints, unit-expression conversion factors and explicit decision binding, the server was restarted and `python3 mvp/tests/test_app_acceptance.py --review-smoke` was executed. Both actual HTTP cases, persisted-record reopening, complete ZIP inventories and source hashes passed. The original six-case matrix above predates this final checker hardening; it was not unnecessarily rerun in full.

| Request | Latest engine run | SysML | Engineering status | Checks | ZIP files |
| --- | --- | --- | --- | --- | --- |
| Candidate A, P2 approved | `20260922T074240-96ff73ec` | PASS | UNKNOWN | 8 PASS, 1 UNKNOWN | 41 |
| Candidate A, P2 not approved | `20260922T074251-ff7ee969` | PASS | FAIL | 7 PASS, 1 FAIL, 1 UNKNOWN | 41 |

`D-UPLOAD-POLICY`, `D-DECISION-BINDING`, `D-UNIT-CONTRACT` and actual topology checks passed in both cases. The unapproved case retained its full-rate upload requirement and failed the uplink budget. Each ZIP now also includes the engine's evidence manifest. Details are in `reviewed-verification-results.json`.

The default review link points to the latest approved candidate A. Its source directory is `mvp/runs/20260922T074240-96ff73ec`.

After the final engine restart, the NASA cFE import button was exercised through Chrome again. It entered the running state, completed official parsing with PASS, and retained engineering acceptance UNKNOWN (engine run `20260922T074439-ef4462ce`). The public-source notice was correct and visible text contained zero Chinese characters.

A compact SVG topology was added using only the approved candidate’s actual `PartUsage` records and resolved `relatedFeature` endpoints. Chrome displayed **10 actual parts and 9 actual connections** in topological columns. Selecting `recordingConnection` opened the official parsed evidence; no fixed graph or manually supplied vessel layout is used. Public reference models retain the generic hierarchy. The final English topology was visually inspected in a CUA screenshot, and the live browser tab is retained for the user. No screenshot file was created.

## Architecture guide UI verification · 2026-09-22

The introductory SVG is explicitly an application-architecture explanation, distinct from the parsed system topology. Its 11 nodes and labeled edges were checked in the browser; node text remained inside its boxes and arrow-label bounding boxes did not overlap. All three path highlights, every node, keyboard Enter, five-stage detail synchronization, guide collapse and both workbench links worked.

Desktop 1354px and mobile 390px showed no page overflow. At 390px the diagram alone scrolls horizontally (323px container, 1100px content). Expanded view, its close button and Escape worked, and temporary viewport overrides were reset. The two helper-text contrast issues found during review were corrected.

The selected approved A record displayed actual lineage: 18 Mbps from configuration row 3, the generated SysML attribute line, the official AttributeUsage identity, and the stored 64.8 / 102.4 GB check with overall UNKNOWN. The old model view still showed 10 parts and 9 resolved connections. History stayed at 14 records; selected case and approval controls remained unchanged. No new engineering run was triggered during architecture QA. JavaScript syntax and unique HTML IDs were checked. Browser screenshots were inspected inline; no screenshot file was saved.

## Concrete harbor case and browser replay · 2026-09-22

The final page section shows a crewed patrol boat inspecting buoy H-07, a mast-mounted dual-view camera, a below-deck equipment box, an antenna, a shore relay and a second vessel. Public hardware references are explicitly concept candidates, not an accepted BOM. Their nominal/typical camera-plus-computer subtotal is 66 W (81 W with the camera heater), before the router and conversion losses; this does not fit the original synthetic 60 W allocation. The existing 54 W model must not be treated as acceptance of these products.

An actual in-app-browser replay generated and encoded two synthetic JPEG images, validated their envelopes, normalized timestamps, calculated SHA-256 hashes, copied and read back the originals in independent memory buffers, generated a resized preview, and transferred its bytes through local MessageChannels to two subscribers. The EO image was 82,363 bytes and the thermal-style illustration was 28,773 bytes. The archive contained 111,136 bytes; the preview was 38,200 bytes. Both subscribers verified the preview hash. The exported JSON was reopened with Python, all three image payloads were decoded, and JPEG signatures, lengths and SHA-256 hashes were independently verified. Evidence is in `mvp/verification/harbor-replay/normal-browser.json` and `normal-verification.json`.

Independent Chrome interaction verified the negative cases: second-based timestamps were rejected at stage 2 without downstream execution; a simulated unavailable link preserved the original archive and queued the preview with zero subscriber deliveries. Public reference history records disabled all replay controls; returning to the approved marine record restored them. At 390 px there was no page overflow: only the vessel drawing scrolled inside its container. Diagram text did not overlap. Temporary viewport overrides were reset.

JavaScript syntax checks and Python server compilation passed. These checks did not run the engineering engine or an LLM, and history remained at 14 records. Canvas imagery is synthetic; its JPEG conversion and local byte transfers execute. No camera, H.264 stream, physical SSD, radio, sustained throughput, thermal measurement or eight-hour retention was tested. Existing SysML engineering acceptance remains UNKNOWN.

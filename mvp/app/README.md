# Local engineering change workbench

A Python standard-library HTTP server and local browser UI. Engineering verdicts come exclusively from `mvp.engine`; the workbench does not simulate parser success or constraint results. Synthetic case inputs and real SysML execution are labeled separately.

Start from the repository root:

```bash
python3 -m mvp.app
```

Open <http://127.0.0.1:8765>. Use `--port 8766` to select another port. The server always binds to `127.0.0.1`. Press Ctrl+C to stop it. Restarting restores records from `mvp/app/data/history/*.json`; `?run=<record_id>` reopens one record. Prior records are not overwritten.

## Engine contract

```python
from mvp.engine import run_case
result = run_case(
    case_name="baseline",
    data_rate_mbps=None,
    link_mbps=None,
    preview_approved=False,
)
```

Supported cases: `baseline`, `upgraded_legacy`, `candidate_a`, `candidate_b`, `degraded_link`. The P2 preview approval checkbox defaults to false and is passed explicitly. Numeric overrides must be finite positive values no greater than 1e9.

The engine must return a JSON-serializable dictionary. The UI recognizes `run_id`, `run_dir`, `status`, `model_path`, `model_text`, `sysml.status`, `sysml.diagnostics`, `checks[]`, `source_manifest`, `model_elements`, and `diff`. Check fields can include `id,label,status,actual,limit,unit,detail`. Unrecognized fields remain in the raw record. Missing results are labeled as missing; no passing verdict is invented.

Use an absolute `run_dir` under `mvp/runs/<run_id>` and preferably an absolute `model_path`. `COMPLETED` describes execution only; the overall engineering status and individual tool/check verdicts are separate. Missing engine returns HTTP 503 / ERROR. Exceptions return 500 / ERROR and persist a record. FAIL and UNKNOWN remain unchanged.

The natural-language endpoint calls `mvp.engine.run_agent(message=..., case_name=..., preview_approved=...) -> dict`. Missing configuration produces an explicit error. No scripted response pretends to be an LLM. The engine owns model-provider configuration and agent run artifacts; this version does not separately persist the chat transcript in workbench history.

## Architecture and data-flow guide

The page opens with an English architecture guide. Its interactive SVG describes the **application architecture**, separate from the actual parsed system topology below. Labeled arrows distinguish HTTP JSON, source rows, generated SysML, semantic JSON/AST, check results and persisted evidence. Nodes explain their input, transformation and output. Manual/agent path controls highlight the same shared engineering tools; the amber agent loop is coded but its provider is unconfigured, and dashed graph retrieval remains proposed. Expand the diagram for a complete view; Escape closes the expanded view.

The source-to-result strip reads the **selected saved record**: its configuration and override provenance, an actual SysML source line, an official parsed attribute identity and the recorded storage check. It never recomputes a verdict in the browser or submits a run. Public reference records explicitly show that maritime lineage does not apply. Further sections map the three papers to implemented, partially borrowed and missing methods, and explain file ownership and usage.

Architecture content lives in `index.html`, `style.css` and `app.js`; it has no external rendering dependency. Node selection, path highlighting and guide controls do not alter case parameters, grant preview approval or invoke engineering tools.

## Harbor inspection case and local observation replay

The final page section, `#harbor-case`, gives the maritime functional model a concrete civilian mission: a patrol boat inspects navigation buoy H-07, retains original visible/thermal-channel observations and shares an operator view with shore and a peer vessel. The scene depicts a mast camera, dry equipment bay, ingestion, edge processing, recorder, cellular router and shore relay. The top guide links directly to it.

Public reference equipment is FLIR M364C, Seeed reComputer Rugged J4012 and Teltonika RUT956. Manufacturer links are shown next to the relevant facts. These products are not an approved BOM: camera 41 W nominal plus computer 25 W typical already totals 66 W before the router/losses, above the existing synthetic 60 W allocation. With the listed 56 W camera heater condition, that subtotal is 81 W. Neither estimate is a measured worst-case profile. The existing 54 W candidate result must not be presented as validation of this assembly.

`harbor-replay.js` independently executes seven browser-local stages:

1. Draw fixed synthetic visible/thermal-style harbor scenes and encode JPEG bytes.
2. Validate the replay envelope, including source, sequence, timestamp units and JPEG signature.
3. Normalize timestamps and hash actual bytes with WebCrypto SHA-256.
4. Copy original bytes into separate memory buffers and verify readback.
5. Produce a resized JPEG only if the selected saved run records preview approval.
6. Transfer via MessageChannel, or retain locally for a simulated outage / failing saved uplink check.
7. Relay to two local subscribers and verify checksums again.

The scene is not camera footage or a thermal measurement. The JPEG preview is not an implementation or validation of the production P2 algorithm. MessageChannel is not a radio test, memory copies are not SSD writes, and the small sample says nothing about sustained Mbps throughput or eight-hour retention. The replay never alters engineering results or approvals and is disabled for public-reference records. Its JSON download contains actual encoded image bytes, hashes, stage receipts, limitations and the associated saved-run identity; reset or page closure clears unexported buffers.

## Actual model view

The model hierarchy is derived from the official export's `model_elements` and `owner` fields. Search by name, qualified name or type; select an element to inspect its raw parsed fields. Connection entries use exported `relatedFeature` references, falling back to `connectorEnd` references with an explicit note that target features are unresolved. For MarineGateway, a compact SVG places actual Gateway part usages in topological columns using the resolved connection endpoints. Select a node or line to inspect the same parsed evidence. Public references retain the generic hierarchy. No fixed vessel diagram or inferred connection is inserted. The model source and full element JSON remain available for inspection.

## HTTP API

| Method and path | Purpose |
| --- | --- |
| `GET /api/status` | Project location, supported cases and active engineering run |
| `POST /api/run` | Engine parameters as JSON; returns `record_id/request/status/result` |
| `POST /api/reference` | JSON `reference_name` (`sysml-official-vehicle` or `nasa-cfe`); calls `engine.run_reference` and persists the actual result |
| `POST /api/agent` | JSON `message/case_name/preview_approved` |
| `GET /api/history` | Latest 500 persisted run summaries |
| `GET /api/runs/<record_id>` | Reopen a complete record |
| `GET /api/runs/<record_id>/export.zip` | All single-run artifacts plus the workbench record |
| `GET /api/sources?record_id=<id>` | Text files from the selected run plus public-data reference examples; without an ID, current project input/model directories |
| `GET /api/source?path=<relative-path>&record_id=<id>` | Read a text file from that inventory |

A process lock prevents concurrent tool execution; conflicts return 409. Records are written atomically. Host and Origin are restricted to the current localhost port. CORS is not enabled. The UI uses `textContent` and does not execute HTML found in input files.

File access is limited to authorized project paths. Real-path checks prevent traversal and escaping symlinks. ZIP exports are restricted to a single directory under `mvp/runs/`; symlinks, hidden paths, files beyond 128 MB total, or more than 2000 files are rejected. The text viewer limit is 2 MB. This is a single-user local demonstration, without enterprise login, role-based approval or remote deployment.

## Verification

Fast application boundary tests:

```bash
python3 -m unittest discover -s mvp/tests -p 'test_app*.py' -v
```

These cover input and approval validation, missing/failed engine, preserving FAIL, history restore, concurrency rejection, source/ZIP traversal, symlinks and cross-site requests. Mock runners in these tests validate the application contract, not SysML correctness.

Explicit real-engine acceptance (start the server first):

```bash
python3 mvp/tests/test_app_acceptance.py
```

This performs actual HTTP runs, checks official parser results and engineering outcomes, reopens records, verifies ZIP completeness, and checks source hashes. See `verification.md` and `verification-results.json` for the actual acceptance evidence and its limits.

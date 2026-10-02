# Synthetic legacy engineering and supplier inputs

**Every material in this directory is an original synthetic test fixture. None is an RTX record, a real supplier document, or evidence from real hardware. The 44/54/68 W values are synthetic engineering budgets, not measurements.**

The application reads its configuration from the actual `legacy.sqlite` database. `configs.json` is a rebuild seed; runtime `get_case_config()` queries SQLite rows without reading that seed. The five tables are `metadata`, `sources`, `configs`, `components`, and `interfaces`. They hold five configurations, seven power-allocation entries per configuration, eight interfaces, and source locators.

Rebuild from the project root:

```bash
python3 mvp/fixtures/build_legacy_db.py
```

Use `--output /absolute/path/legacy.sqlite` to build another snapshot. The renderer builds the default database only if it is missing; it never silently overwrites an existing snapshot.

## Data semantics

| Case | Aggregate raw Mbit/s | Recorder GB | Node W | Default link Mbit/s |
|---|---:|---:|---:|---:|
| baseline | 6 | 64 | 44 | 8 |
| upgraded_legacy | 18 | 64 | 44 | 8 |
| candidate_a | 18 | 128 | 54 | 8 |
| candidate_b | 18 | 128 | 68 | 8 |
| degraded_link | 18 | 128 | 54 | 1.5 |

The rates aggregate both payloads. Retention is 8 hours, storage uses decimal GB, and 80% is the net quota for original raw data. Upload traffic incurs a factor of 1.2 for network overhead. That factor does not also inflate storage. A shore relay duplicates data to two subscribers after one platform-to-shore uplink.

`requirements.json` records 18 synthetic requirements, assumptions, unknowns, and replacement rules. Candidates A/B/degraded **default to full real-time raw upload**. Only explicit `preview_approved=True` selects the fixed 2 Mbit/s P2 profile and adds the preview processor and connection. The original recording path remains intact. The generator does not invent an approver; the application must bind a real runtime decision record. Preview quality criteria and maximum latency remain unspecified and are not established by passing a resource budget.

Each of the two supplier inputs in `suppliers/` has an ICD JSON and a separate `.sysml` package. The system model imports both packages. Payload and shared-message timestamps explicitly use milliseconds. `reuse_packages.json` records candidate provenance, applicability conditions, and the condition that prevents candidate B from meeting the current power budget.

## Rendering API

```python
from mvp.models.render_model import get_case_config, render_model, write_model_package

config = get_case_config("candidate_a", data_rate_mbps=18, preview_approved=True)
text = render_model("degraded_link", preview_approved=True)
paths = write_model_package("/tmp/marine-case", "candidate_a", 30, 8, preview_approved=True)
```

The shared arguments are `(case_name, data_rate_mbps=None, link_mbps=None, *, preview_approved=False)`. `write_model_package` additionally takes `output_dir` first. Aliases include `unchanged` for `upgraded_legacy` and `A`/`B` for their corresponding candidates.

`write_model_package()` returns `model_path`, `model_files`, `requirements_path`, `mapping_path`, `manifest_path`, and `config`. Returned paths are absolute. The package includes the system model, both supplier packages and ICDs, selected requirements, source mappings, the database snapshot, reuse packages, original source JSON snapshots, and a file SHA-256 manifest. Each run should use a new output directory. Original source files are verified against the hashes stored in SQLite before being copied. Changed seed files require an explicit database rebuild. The source mapping retains the selected configuration, component, and interface row IDs and database hash; inserting P2 is recorded as a requirement-driven interface change.

The main package is `MarineGateway`. Budget inputs under `MarineGateway::gateway` are `dataRateMbps`, `retentionHours`, `storageGB`, `usableFraction`, `linkMbps`, `networkFactor`, `uploadRateMbps`, `previewMbps`, `totalPowerW`, `powerLimitW`, and `previewApproved`. Power and time also use the official library's `PowerValue` and `TimeValue` types. Data rates and storage are `Real` values with explicit unit annotations.

The template uses official Pilot examples for requirement subjects, satisfaction, verification, ports and conjugation, and action performance. **Rendering files does not validate a model.** Each generated revision must be checked using the real parser, libraries, and engineering checks. A `satisfy` relationship declares design intent; a verification definition is not a successful result. A newly rendered manifest therefore starts with `validation_status: NOT_RUN`.

During implementation, both the raw-upload and approved-P2 model forms passed the actual official Pilot Xtext/EMF parser and linker without diagnostics. Those observations apply to the tested revisions only; consult each run's validation record for the current model and toolchain hashes. They do not establish complete standard conformance, task quality, latency, or real hardware behavior.

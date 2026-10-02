# Project-local official SysML v2 toolchain

This directory contains a working Java 21 setup and a headless adapter that uses the official SysML Pilot parser, linker, Xtext validator, EMF model and JSON exporter. It does not recognize model text with regular expressions, inspect console text to decide success, or substitute configured values for parsed values.

## Versions actually installed and exercised

- Eclipse Temurin JDK **21.0.12.1+1**, Linux x64, under `java21/`; package URL and verified vendor SHA-256 in `java.lock.json`.
- Official Pilot release **2026-08**, kernel **0.62.0**, packaged shaded JAR under `kernel/sysml/`; official release asset SHA-256 in `kernel.lock.json`.
- Standard libraries from `vendor/SysML-v2-Release/sysml.library`, pinned to Git commit `fb97b754f29588b8e9c7a35f370880cd15eb29e7`. Each validation saves a complete `library-manifest.json` with file hashes and aggregate content hash.
- The parent task checked out the full Pilot source at release tag `2026-08`, matching the packaged kernel. The JAR is an upstream prebuilt artifact; this work does **not** claim to have built all upstream modules from source.

This implementation release includes SysML 2.1 development material. It is a real SysML v2 implementation; use of this release is not certification of complete conformance to the SysML 2.0 specification. Language version, implementation version and library version remain separate records.

No system Java, alternatives, shell profile or user Jupyter settings were changed. Java 11 remains the system default. Java and kernel downloads are ignored by Git; bootstrap scripts and lock records are retained. Direct validation requires only Python's standard library and this local JDK/JAR. Maven and a Jupyter server are unnecessary.

## Bootstrap and repeat a validation

Run from the project root after cloning the official Release repository into the pinned `vendor/` location:

```bash
python3 mvp/toolchain/bootstrap_java.py
python3 mvp/toolchain/bootstrap_kernel.py
python3 mvp/toolchain/validate.py --package Smoke --output mvp/toolchain/runs/check-001 mvp/toolchain/smoke-models/valid.sysml mvp/toolchain/smoke-models/types.sysml
```

Choose a fresh or empty output directory for each invocation. Existing evidence is never overwritten. The first invocation compiles the small adapter with the local `javac`; subsequent invocations reuse the compiled class only when source and JAR hashes match. Each validation starts a fresh JVM, loads all supplied files before resolving references, then runs the official validator in `CheckMode.ALL`. The two-file smoke example intentionally supplies the consuming file before the type declaration.

Python API:

```python
from mvp.toolchain.validate import validate_package

result = validate_package(
    model_files=["path/to/system.sysml", "path/to/types.sysml"],
    package_name="SystemModel",
    output_dir="path/to/new-run/validation",
)
```

The result includes `status`, `diagnostics`, `model_json_path`, `ast_json_path` on success, input hashes, toolchain identifiers, warning count, return code, elapsed time, and actual stdout/stderr log paths. CLI exit codes are `0` for language PASS, `2` for language FAIL, and `3` for tool ERROR. Invalid caller arguments raise Python exceptions. A run times out after 180 seconds by default. The source hashes are checked again after validation; a concurrent source edit invalidates the result.

`request.json` and `validation.json` record the exact command. The actual headless JVM command is:

```text
<project>/mvp/toolchain/java21/bin/java -Xmx1536m -Dfile.encoding=UTF-8 -cp <build>:<official-kernel.jar> SysMLHeadless <run>/request.json
```

Paths containing spaces are passed as subprocess argument arrays, not shell strings.

## Actual model and diagnostic outputs

- `model.json` is the **unmodified official API-model delta JSON** from `SysMLInteractive.export()`: an array of `{identity, payload}` records. A payload has `@id`, `@type`, named features and references. The primary requested package and referenced user elements are traversed by the official exporter. This does not stand in for saving all source files/dependencies in an engineering package.
- An `AttributeUsage` is not itself a raw number. Its `FeatureValue` refers to a `LiteralInteger`/`LiteralRational`, whose `value` is the parsed numeric value. General arithmetic expressions require evaluation or a deliberately supported expression evaluator; no scalar fallback is supplied.
- `ast-elements.json` is a supplemental **EMF-derived** source-location index. Each element has its class, identity, name, qualified name and source file/line/offset where available. Its `references` map expands every noncontainment EReference one level, including resolved library target names; it is not a second editable model.
- Unit shorthand is resolved by the actual model: `54 [W]` refers to `SI::watt`; `54 [m]` refers to `SI::metre`. Inspect `FeatureReferenceExpression.references.referent`. Do not hard-code names as `SI::W` or rely on filenames or unit suffixes.
- `diagnostics` preserve original Xtext severity, issue code, message, line, column, offset, length and syntax-error flag. Adapter failures have an explicit adapter code. Warnings are not silently reclassified as official errors.

## Verified behavior and limitations

The executable smoke test is:

```bash
python3 mvp/toolchain/smoke_test.py
```

It writes a fresh evidence directory under `smoke-results/integration-*` and checks:

1. A real cross-file model loads, links and exports.
2. Changing the actual source value from 18.0 to 30.0 changes the official exported literal.
3. A nonexistent part type produces real linking/static errors, with source positions and no valid model export.
4. A syntax error produces a real syntax diagnostic.
5. An Integer assigned a String currently receives an official **WARNING**, not an ERROR.
6. A `PowerValue = 54 [W]` model resolves the unit to `SI::watt`.
7. A `PowerValue = 54 [m]` model currently gets no official error, but its resolved reference is `SI::metre` and fails the smoke fixture's explicit watt-unit contract.

Consequently language `PASS` does **not** prove unit/dimension correctness, requirement satisfaction, or power/storage/bandwidth feasibility. The application must apply separate engineering gates. The unit fixture comparison proves the adapter exposes actual semantic references; it is not a general-purpose units solver. The application may block relevant warnings under its own policy while retaining the upstream severity.

The baseline smoke evidence in `smoke-results/summary.json` and the final integration summary record measured results, including failures. The direct headless path has been executed. A project-local Python environment with a Jupyter client was prepared while investigating alternatives, but is not needed by the implemented adapter and no interactive Jupyter UI test is claimed.

## Upstream implementation basis

- [Official kernel README](https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation/blob/2026-08/org.omg.sysml.jupyter.kernel/README.adoc): Java 21+, kernel distribution and library configuration.
- [Official 2026-08 distribution](https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation/releases/tag/2026-08): checksum-pinned binary used here.
- [Official SysMLInteractive implementation](https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation/blob/2026-08/org.omg.sysml.interactive/src/org/omg/sysml/interactive/SysMLInteractive.java): instance setup, library loading, scope resolution and JSON export.
- [Official SysMLUtil implementation](https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation/blob/2026-08/org.omg.sysml/src/org/omg/sysml/io/SysMLUtil.java): resource set, indexing and cross-file resolution.

Upstream licenses remain in the downloaded/cloned distributions. The runtime downloads are relocatable project dependencies, not globally installed software.

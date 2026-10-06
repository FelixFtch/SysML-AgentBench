"""Draw any SysML v2 model the official Pilot has parsed, for the results page and the report.

General: it works from a run folder of the official tool (mvp/runs/<run id>: the model files, the official parse and
the request), whatever the task, so every exam answer, console run, Part 2 design and MOD change can be drawn without
per-model work.

Two views:
- connections: every part usage as a box, nested as the model nests it (a usage typed by a definition shows that
  definition's parts, ports and attribute values), ports as small boxes, and every connection of the package, all
  read from the same official parse the scorer reads; an alignment package's `alias` and `allocate` statements are
  drawn as arrows between the names they map. The Pilot 0.62 visualizer leaves out connections declared at package
  level (`connect usv.camera.imagery to usv.processor.imageryIn;`), which is how most models here declare them, so
  this view is drawn here and laid out with Graphviz.
- tree: the Pilot's own %viz TREE view (definitions, usages, typing, ports), through bench/viz/SysMLViz.java.

    python3 bench/model_diagram.py <run id> [--view connections|tree] [--png]

Output: analysis/diagrams/<run id>-<view>.svg, cached: a run folder does not change after the parse.
Graphviz is the conda-forge build in tools/graphviz (`micromamba create -p tools/graphviz -c conda-forge graphviz`).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mvp.engine import ModelView, exported_elements  # noqa: E402

RUNS = ROOT / "mvp" / "runs"
OUT = ROOT / "analysis" / "diagrams"
DOT = ROOT / "tools" / "graphviz" / "bin" / "dot"
TOOLCHAIN = ROOT / "mvp" / "toolchain"
JAVA_BIN = TOOLCHAIN / "java21" / "bin"
JAR = TOOLCHAIN / "kernel" / "sysml" / "jupyter-sysml-kernel-0.62.0-all.jar"
VIZ_SOURCE = ROOT / "bench" / "viz" / "SysMLViz.java"
VIZ_BUILD = ROOT / "bench" / "viz" / "build"
RUN_ID = re.compile(r"^\d{8}T\d{6}-[0-9a-f]{8}$")
VIEWS = ("connections", "tree")
PARTS = {"PartUsage", "ItemUsage"}
LINKS = {"ConnectionUsage", "InterfaceUsage", "FlowConnectionUsage", "SuccessionFlowConnectionUsage", "FlowUsage",
         "BindingConnectorAsUsage", "AllocationUsage"}
MAX_DEPTH = 6
# One JVM at a time: the tree view loads the whole standard library.
LOCK = threading.Lock()


class DiagramError(RuntimeError):
    pass


def run_folder(run_id: str) -> Path:
    if not RUN_ID.match(run_id or ""):
        raise DiagramError(f"Not a run id: {run_id!r}")
    folder = RUNS / run_id
    if not (folder / "sysml" / "request.json").is_file():
        raise DiagramError(f"No official parse for run {run_id}")
    return folder


def _name(element: dict) -> str:
    return element.get("declaredName") or element.get("name") or ""


def _types(view: ModelView, element: dict) -> list[str]:
    return [_name(view.by_id[ref["@id"]]) for ref in element.get("type") or [] if ref.get("@id") in view.by_id]


def _features(view: ModelView, element: dict) -> list[dict]:
    """Owned features first, then inherited ones; one per name, so a redefinition hides what it redefines."""
    seen, out = set(), []
    for key in ("ownedFeature", "feature"):
        for ref in element.get(key) or []:
            child = view.by_id.get(ref.get("@id"))
            if not child or not _name(child) or _name(child) in seen:
                continue
            if child.get("@type") in PARTS or child.get("@type") in {"PortUsage", "AttributeUsage"}:
                seen.add(_name(child))
                out.append(child)
    return out


def _value(view: ModelView, attribute: dict) -> str | None:
    link = view.value_links.get(attribute["@id"])
    if not link:
        return None
    value = view.by_id.get((link.get("value") or {}).get("@id"), {})
    if value.get("@type") in {"LiteralInteger", "LiteralRational", "LiteralBoolean", "LiteralString"}:
        text = str(value.get("value"))
    else:
        text = "expression"
    try:
        units = sorted(unit.split("::")[-1] for unit in view.units_in_expression(attribute.get("qualifiedName") or ""))
    except Exception:
        units = []
    return f"{text} {' '.join(units)}".strip()


def _expand(view: ModelView, element: dict, path: str, depth: int, chain: frozenset, paths_of: dict) -> dict:
    node = {"path": path, "label": f"{_name(element)}" + (f" : {', '.join(_types(view, element))}" if _types(view, element) else ""),
            "ports": [], "attrs": [], "parts": []}
    paths_of[element["@id"]].append(path)
    for ref in element.get("type") or []:
        paths_of[ref.get("@id")].append(path)
    if depth >= MAX_DEPTH or element["@id"] in chain:
        return node
    for child in _features(view, element):
        child_path = f"{path}.{_name(child)}"
        kind = child.get("@type")
        if kind == "PortUsage":
            types = _types(view, child)
            node["ports"].append({"path": child_path, "label": _name(child), "type": ", ".join(types)})
            paths_of[child["@id"]].append(child_path)
        elif kind == "AttributeUsage":
            value = _value(view, child)
            if value is not None:
                node["attrs"].append(f"{_name(child)} = {value}")
        else:
            node["parts"].append(_expand(view, child, child_path, depth + 1, chain | {element["@id"]}, paths_of))
    return node


def model_graph(run_id: str) -> dict:
    """Parts, ports, attribute values and connections of one officially parsed model, as instance paths."""
    folder = run_folder(run_id)
    request = json.loads((folder / "sysml" / "request.json").read_text(encoding="utf-8"))
    if not (folder / "sysml" / "model.json").is_file():
        raise DiagramError(f"Run {run_id} did not pass the official parse, so there is no model to draw")
    package = request["package_name"]
    elements = exported_elements(json.loads((folder / "sysml" / "model.json").read_text(encoding="utf-8")))
    ast_path = folder / "sysml" / "ast-elements.json"
    view = ModelView(elements, json.loads(ast_path.read_text(encoding="utf-8")) if ast_path.is_file() else [])
    top = view.by_name.get(package)
    owned_by_top = [e for e in elements if top and (e.get("owningNamespace") or {}).get("@id") == top["@id"]]
    roots = [e for e in owned_by_top if e.get("@type") in PARTS]
    if not roots:
        roots = [e for e in owned_by_top if e.get("@type") in {"PartDefinition", "ItemDefinition"}]
    paths_of: dict = defaultdict(list)
    tree = [_expand(view, root, _name(root), 0, frozenset(), paths_of) for root in roots if _name(root)]
    links = []
    for member in elements:
        # `alias X for Y` (an alignment package's mapping): a non-owning membership of the package itself.
        if member.get("@type") == "Membership" and top and (member.get("membershipOwningNamespace") or {}).get("@id") == top["@id"]:
            target = view.by_id.get((member.get("memberElement") or {}).get("@id"), {}).get("qualifiedName") \
                or view.reference_name((member.get("memberElement") or {}).get("@id", ""))
            if member.get("memberName") and target:
                links.append({"from": member["memberName"], "to": target, "kind": "alias", "label": "alias"})
    for link in elements:
        if link.get("@type") not in LINKS:
            continue
        ends = [view.reference_name(ref["@id"]) for ref in link.get("relatedFeature") or []]
        if len(ends) < 2 or not all(ends):
            continue
        owner = view.by_id.get((link.get("owningNamespace") or {}).get("@id"), {})
        owner_name = owner.get("qualifiedName") or package
        if owner_name != package and not owner_name.startswith(package + "::"):
            continue  # a connection of another model parsed alongside, e.g. an alignment's source model
        bases = [""] if owner_name == package else (paths_of.get(owner.get("@id")) or [""])
        prefix = (package if owner_name == package else owner_name) + "::"
        for base in sorted(set(bases)):
            points = []
            for end in ends[:2]:
                if end.startswith(prefix):
                    rel = end[len(prefix):].replace("::", ".")
                    points.append(f"{base}.{rel}" if base else rel)
                else:
                    # Outside this package, e.g. the two source models an alignment package allocates between.
                    points.append(end)
            links.append({"from": points[0], "to": points[1], "kind": link["@type"], "label": _name(link)})
    return {"run_id": run_id, "package": package, "parts": tree, "links": links}


def _q(text: str) -> str:
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def to_dot(graph: dict) -> str:
    known: set[str] = set()
    title = f"{graph['package']} · drawn from the official parse of run {graph['run_id']}"
    lines = ['digraph model {',
             '  graph [rankdir=LR, fontname="Helvetica", fontsize=11, nodesep=0.22, ranksep=0.6, pad=0.15];',
             '  node [fontname="Helvetica", fontsize=10, shape=box, style="rounded,filled", fillcolor="#fffbe8", color="#9a8a55"];',
             '  edge [fontname="Helvetica", fontsize=9, color="#1f5f99", penwidth=1.4, arrowhead=none];',
             f'  label={_q(title)}; labelloc=t; labeljust=l;']

    def emit(node: dict, indent: str) -> None:
        known.add(node["path"])
        if not node["ports"] and not node["parts"] and not node["attrs"]:
            lines.append(f'{indent}{_q(node["path"])} [label={_q(node["label"])}];')
            return
        lines.append(f'{indent}subgraph {_q("cluster_" + node["path"])} {{')
        lines.append(f'{indent}  label={_q(node["label"])}; style="rounded,filled"; fillcolor="#f5f8fb"; color="#7a9bb5"; fontsize=10;')
        lines.append(f'{indent}  {_q(node["path"])} [shape=point, width=0.01, style=invis];')
        for port in node["ports"]:
            known.add(port["path"])
            tip = f'{port["label"]} : {port["type"]}' if port["type"] else port["label"]
            lines.append(f'{indent}  {_q(port["path"])} [label={_q(port["label"])}, tooltip={_q(tip)}, shape=box, style=filled, '
                         f'fillcolor="#dbeafe", color="#5b84b1", fontsize=9, height=0.25, margin="0.06,0.02"];')
        if node["attrs"]:
            lines.append(f'{indent}  {_q(node["path"] + "#values")} [shape=plaintext, style="", fontsize=9, '
                         f'label={_q(chr(10).join(node["attrs"]))}];')
        for part in node["parts"]:
            emit(part, indent + "  ")
        lines.append(f"{indent}}}")

    for root in graph["parts"]:
        emit(root, "  ")
    for link in graph["links"]:
        for point in (link["from"], link["to"]):
            if point not in known:
                known.add(point)
                lines.append(f'  {_q(point)} [label={_q(point)}, fillcolor="#ffffff", color="#8a96a3", tooltip="not a part of this package"];')
        style = {"BindingConnectorAsUsage": 'style=dashed',
                 "AllocationUsage": 'style=dashed, arrowhead=normal, color="#7a4fb0", fontcolor="#7a4fb0", label="allocate"',
                 "alias": 'style=dashed, arrowhead=normal, color="#2f7d4f", fontcolor="#2f7d4f", label="alias"'}.get(link["kind"], "")
        if link["kind"] in {"FlowConnectionUsage", "SuccessionFlowConnectionUsage", "FlowUsage"}:
            style = "arrowhead=normal"
        label = f'label={_q(link["label"])}' if link["label"] and "label=" not in style else ""
        attrs = ", ".join(item for item in (style, label) if item)
        lines.append(f'  {_q(link["from"])} -> {_q(link["to"])}{f" [{attrs}]" if attrs else ""};')
    lines.append("}")
    return "\n".join(lines) + "\n"


def _dot(source: str, fmt: str) -> bytes:
    if not DOT.is_file():
        raise DiagramError(f"Graphviz is missing: {DOT} (micromamba create -p tools/graphviz -c conda-forge graphviz)")
    done = subprocess.run([str(DOT), f"-T{fmt}"], input=source.encode("utf-8"), capture_output=True, timeout=120)
    if done.returncode != 0:
        raise DiagramError(f"Graphviz failed: {done.stderr.decode('utf-8', 'replace')[:400]}")
    return done.stdout


def _viz_class() -> Path:
    built = VIZ_BUILD / "SysMLViz.class"
    if not built.is_file() or built.stat().st_mtime < VIZ_SOURCE.stat().st_mtime:
        VIZ_BUILD.mkdir(parents=True, exist_ok=True)
        done = subprocess.run([str(JAVA_BIN / "javac"), "-cp", str(JAR), "-d", str(VIZ_BUILD), str(VIZ_SOURCE)],
                              capture_output=True, text=True, timeout=300)
        if done.returncode != 0:
            raise DiagramError(f"Could not compile SysMLViz.java: {done.stderr[-400:]}")
    return built


def _tree(folder: Path, svg: Path, png: bool) -> None:
    request = json.loads((folder / "sysml" / "request.json").read_text(encoding="utf-8"))
    job = {"library_path": request["library_path"], "model_files": request["model_files"], "names": [request["package_name"]],
           "views": ["TREE"], "styles": ["STDCOLOR"], "output_svg": str(svg), "graphviz_dot": str(DOT)}
    if png:
        job["output_png"] = str(svg.with_suffix(".png"))
    job_path = svg.with_suffix(".request.json")
    job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if key != "DISPLAY"}
    with LOCK:
        _viz_class()
        subprocess.run([str(JAVA_BIN / "java"), "-Djava.awt.headless=true", "-Xmx1536m", "-cp", f"{VIZ_BUILD}{os.pathsep}{JAR}",
                        "SysMLViz", str(job_path)], capture_output=True, text=True, timeout=300, env=env)
    result = json.loads(svg.with_suffix(".json").read_text(encoding="utf-8"))
    if result.get("status") != "OK":
        raise DiagramError(f"The Pilot could not draw the model: {result.get('message', '')[:400]}")


def render(run_id: str, view: str = "connections", *, png: bool = False) -> Path:
    """The SVG of one view of one run, drawn once and then read from analysis/diagrams/."""
    if view not in VIEWS:
        raise DiagramError(f"Unknown view {view!r}; use one of {', '.join(VIEWS)}")
    folder = run_folder(run_id)
    OUT.mkdir(parents=True, exist_ok=True)
    svg = OUT / f"{run_id}-{view}.svg"
    if svg.is_file() and (not png or svg.with_suffix(".png").is_file()):
        return svg
    if view == "tree":
        if json.loads((folder / "sysml" / "validation.json").read_text(encoding="utf-8")).get("status") != "PASS":
            raise DiagramError(f"Run {run_id} did not pass the official parse, so there is no model to draw")
        _tree(folder, svg, png)
        return svg
    source = to_dot(model_graph(run_id))
    svg.with_suffix(".dot").write_text(source, encoding="utf-8")
    svg.write_bytes(_dot(source, "svg"))
    if png:
        svg.with_suffix(".png").write_bytes(_dot(source, "png"))
    return svg


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_id")
    parser.add_argument("--view", choices=VIEWS, default="connections")
    parser.add_argument("--png", action="store_true", help="also write a PNG next to the SVG")
    args = parser.parse_args()
    print(render(args.run_id, args.view, png=args.png))


if __name__ == "__main__":
    main()

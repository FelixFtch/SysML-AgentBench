# ALN-03 — synthetic, not an RTX specification

Align two independently written models of the UAV sensors: definitions versus instances. The specification package is `UavSensorSpec`; the supplier package is `RadarVendor`. Both are given below as baseline files and must not be changed.

Write one SysML v2 alignment package named AlignRadar. It must:
1. Import both source packages; declare nothing new except aliases and allocations. Do not copy or edit the source models.
2. For each definition, port or attribute of the specification that corresponds to one supplier element, declare `alias <SpecificationShortName> for <Supplier::Qualified::Name>;` using the supplier element's fully qualified name.
3. For each part usage of the specification that corresponds to a supplier part usage, declare `allocation <name> allocate <Spec::path.with.dots> to <Supplier::path.with.dots>;` with fully qualified usage paths.
4. Leave elements without a counterpart unmapped; do not force a pair when the meaning differs.
Then, in one fenced json block, report {"mappings": [{"oem_element": "...", "supplier_element": "...", "mapping_type": "alias|allocation", "rationale": "..."}], "unmatched": ["qualified names with no counterpart"]}.
Reply with one fenced sysml block followed by one fenced json block, and no other text.

# Synthetic maritime ISR ground truth

Human-authored reference model for the benchmark. Agents must not be shown this directory.

`MaritimeISR.sysml` is the four-node system: unmanned surface vessel, fixed-wing UAV, command ship, and shore station. All numeric limits are synthetic and are not RTX specifications.

Official Pilot validation on 2026-10-02: PASS, 50 named elements, run `20261002T231323-aea6edfc`. No domain budget checker was applied, so engineering acceptance stays UNKNOWN.

`assertions.yaml` is the scoring checklist derived from that parsed model. It has one author. A second review is still pending, so this gold is not frozen.

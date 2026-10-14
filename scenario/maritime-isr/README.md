# Synthetic maritime ISR ground truth

Human-authored reference model for the benchmark. Agents must not be shown this directory.

`MaritimeISR.sysml` is the four-node system: unmanned surface vessel, fixed-wing UAV, command ship, and shore station. All numeric limits are synthetic and are not RTX specifications.

Official Pilot validation on 2026-10-02: PASS, 50 named elements, run `20261002T231323-aea6edfc`. No domain budget checker was applied, so engineering acceptance stays UNKNOWN.

`assertions.yaml` is the scoring checklist derived from that parsed model. It has one author. A second review of this file is still pending, so this checklist is not frozen.

That is not the status of the exam. The 27 held-out answer keys were read by a second reviewer on 2026-10-06 and frozen (`bench/tasks/t4_maritime_isr/heldout/REVIEW.md`, decision 028). Those keys are a different artifact. This directory is the reference model they start from.

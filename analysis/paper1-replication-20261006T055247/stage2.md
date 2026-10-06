# Stage 2: Match Candidate Suggestion (Alias + Extension Based)

Operating in **best-effort mode**. All proposed mappings are derived from syntactic context, name similarity, shallow type roles, and deeper semantic alignment using the uploaded `AllocationExtension` library.

---

## 1. Matching Logic & Extension Application

*   **Alias Mapping:** Applied to elements with high name similarity and compatible structural/behavioral roles. Aliases provide symbol-level resolution without altering underlying definitions.
*   **Extension-Based Mapping:** The `AllocationExtension` metadata definitions (`FullyMatched`, `RequireModification`, `RequireComplement`, `FullyUnMatched`) are applied as semantic tags to indicate the depth of alignment. Because these extensions target `AllocationUsage`, they are recommended to be instantiated on allocation relationships between mapped elements in Stage 4.
    *   `FullyMatched`: Elements are semantically and structurally equivalent.
    *   `RequireModification`: Elements serve the same role but differ in types, attributes, or internal structure (e.g., OEM uses `ISQ::mass` for a port payload, Supplier uses a derived `millivolt` scalar).
    *   `RequireComplement`: An element exists in one model but has no counterpart in the other; integration requires creating a complementary mapping or accepting asymmetry.
    *   `FullyUnMatched`: Explicitly flagged for elements where mapping was considered but rejected due to semantic incompatibility.

---

## 2. Candidate Mappings JSON Output

```json
[
  {
    "oem_element": "OEMRequirements::OEMGeneralDefinition::GeneralPartDefinition::def_OverallSystem",
    "supplier_element": "LoadCellSolution::Definition::Partdefinition::MeasuringSystem_def",
    "mapping_type": "alias",
    "extension_tag": "FullyMatched",
    "confidence": 0.95,
    "rationale": "Both represent the top-level system part definition containing load cells and energy systems. Structural hierarchy is highly consistent."
  },
  {
    "oem_element": "OEMRequirements::OEMGeneralDefinition::GeneralPartDefinition::def_LoadCell",
    "supplier_element": "LoadCellSolution::Definition::Partdefinition::loadcell_def",
    "mapping_type": "alias",
    "extension_tag": "RequireModification",
    "confidence": 0.90,
    "rationale": "Core load cell definitions match. However, Supplier adds temperature attributes (Tmax, Tmin) and weight, and uses different port definitions for mass and measuring info."
  },
  {
    "oem_element": "OEMRequirements::OEMGeneralDefinition::GeneralPartDefinition::def_EnergySystem",
    "supplier_element": "LoadCellSolution::Definition::Partdefinition::EnergySystem_def",
    "mapping_type": "alias",
    "extension_tag": "RequireModification",
    "confidence": 0.85,
    "rationale": "Functional equivalence, but OEM output port types to def_port_Energy while Supplier types to port_Power_def."
  },
  {
    "oem_element": "OEMRequirements::OEMGeneralDefinition::GeneralPortDefinition::def_port_MeasuringInfo",
    "supplier_element": "LoadCellSolution::Definition::PortDefinition::port_MeasuringInfo_def",
    "mapping_type": "alias",
    "extension_tag": "RequireModification",
    "confidence": 0.75,
    "rationale": "Semantic intent matches, but payload differs significantly. OEM outputs ISQ::mass directly; Supplier derives a millivolt scalar from ISQ::voltage."
  },
  {
    "oem_element": "OEMRequirements::OEMGeneralDefinition::GeneralPortDefinition::def_port_Energy",
    "supplier_element": "LoadCellSolution::Definition::PortDefinition::port_Power_def",
    "mapping_type": "alias",
    "extension_tag": "FullyMatched",
    "confidence": 0.95,
    "rationale": "Both define an input port carrying ISQ::voltage. Naming differs (Energy vs Power) but electrical semantics are identical."
  },
  {
    "oem_element": "OEMRequirements::OEMGeneralDefinition::GeneralPortDefinition::def_port_Mass",
    "supplier_element": "LoadCellSolution::Definition::PortDefinition::port_Mass_def",
    "mapping_type": "alias",
    "extension_tag": "RequireModification",
    "confidence": 0.70,
    "rationale": "OEM accepts ISQ::mass directly. Supplier accepts an 'item measuringObject'. Requires type adaptation or complement."
  },
  {
    "oem_element": "OEMRequirements::OEMGeneralDefinition::GeneralInterfaceDefinition::def_MessDataInterface",
    "supplier_element": "LoadCellSolution::Definition::InterfaceDefinition::MessDataInterface_def",
    "mapping_type": "alias",
    "extension_tag": "RequireModification",
    "confidence": 0.80,
    "rationale": "Interfaces connect corresponding measuring ports. Flow feature names differ (MessData vs MessInfo) and underlying port payloads differ."
  },
  {
    "oem_element": "OEMRequirements::OEMGeneralDefinition::GeneralInterfaceDefinition::def_EnergyInterface",
    "supplier_element": "LoadCellSolution::Definition::InterfaceDefinition::PowerInterface_def",
    "mapping_type": "alias",
    "extension_tag": "FullyMatched",
    "confidence": 0.95,
    "rationale": "Both route voltage between power/energy ports. Feature flow names differ (inputVoltage vs inputVolt) but types match perfectly."
  },
  {
    "oem_element": "OEMRequirements::LoadCellSubsystemRequirement::OverallSystemModel::PartsTree::OverallSystem_v1",
    "supplier_element": "LoadCellSolution::LoadCellSolutionModel::PartsTree::MeasuringSystem_v1",
    "mapping_type": "alias",
    "extension_tag": "FullyMatched",
    "confidence": 0.95,
    "rationale": "Top-level part usages instantiating the overall system definitions. Both redefine Loadcellnumber to 3."
  },
  {
    "oem_element": "OEMRequirements::LoadCellSubsystemRequirement::OverallSystemModel::PartsTree::OverallSystem_v1::loadcell",
    "supplier_element": "LoadCellSolution::LoadCellSolutionModel::PartsTree::MeasuringSystem_v1::loadcell_v1",
    "mapping_type": "alias",
    "extension_tag": "RequireModification",
    "confidence": 0.90,
    "rationale": "Load cell part usages. Both set voltage to 12[V] and redefine maximumCapacity. Supplier explicitly sets capacity to 40[kg] and adds mass/strain gauge."
  },
  {
    "oem_element": "OEMRequirements::LoadCellSubsystemRequirement::OverallSystemModel::PartsTree::OverallSystem_v1::EnergySystem",
    "supplier_element": "LoadCellSolution::LoadCellSolutionModel::PartsTree::MeasuringSystem_v1::EnergySystem",
    "mapping_type": "alias",
    "extension_tag": "FullyMatched",
    "confidence": 0.98,
    "rationale": "Exact name match, identical functional role within the parent part hierarchy."
  },
  {
    "oem_element": "OEMRequirements::LoadCellSubsystemRequirement::OverallSystemModel::PartsTree::OverallSystem_v1::energyInterface",
    "supplier_element": "LoadCellSolution::LoadCellSolutionModel::PartsTree::MeasuringSystem_v1::energyInterface",
    "mapping_type": "alias",
    "extension_tag": "FullyMatched",
    "confidence": 0.90,
    "rationale": "Both instantiate their respective energy/power interface definitions and connect EnergySystem output to LoadCell input."
  },
  {
    "oem_element": "N/A",
    "supplier_element": "LoadCellSolution::Definition::Partdefinition::StrainGauge_def",
    "mapping_type": "extension",
    "extension_tag": "RequireComplement",
    "confidence": 1.0,
    "rationale": "Supplier defines a Strain Gauge component absent in the OEM model. Requires complement if strict parity is desired."
  },
  {
    "oem_element": "N/A",
    "supplier_element": "LoadCellSolution::Definition::PortDefinition::port_Temperature_def",
    "mapping_type": "extension",
    "extension_tag": "RequireComplement",
    "confidence": 1.0,
    "rationale": "Supplier introduces temperature monitoring ports not present in OEM architecture."
  },
  {
    "oem_element": "N/A",
    "supplier_element": "LoadCellSolution::Definition::InterfaceDefinition::TemperatureInterface_def",
    "mapping_type": "extension",
    "extension_tag": "RequireComplement",
    "confidence": 1.0,
    "rationale": "Supplier interface for temperature routing. No OEM counterpart."
  },
  {
    "oem_element": "N/A",
    "supplier_element": "LoadCellSolution::Definition::ItemDefinition::def_MeasuringObject",
    "mapping_type": "extension",
    "extension_tag": "RequireComplement",
    "confidence": 1.0,
    "rationale": "Supplier defines an explicit Item for the measuring object, whereas OEM passes ISQ::mass directly through the port."
  }
]
```
*(Note: In a production environment, this JSON block should be saved as `Stage2_CandidateMappings.json` for downstream tool integration.)*

---

## 3. Human-Readable Summary Table

| OEM Element | Supplier Element | Match Type | Extension Tag | Confidence | Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `...::def_OverallSystem` | `...::MeasuringSystem_def` | alias | FullyMatched | 0.95 | Top-level system definitions align structurally and hierarchically. |
| `...::def_LoadCell` | `...::loadcell_def` | alias | RequireModification | 0.90 | Core roles match, but Supplier adds temp attributes and alters port types. |
| `...::def_EnergySystem` | `...::EnergySystem_def` | alias | RequireModification | 0.85 | Functional match, but output port types differ (Energy vs Power port defs). |
| `...::def_port_MeasuringInfo` | `...::port_MeasuringInfo_def` | alias | RequireModification | 0.75 | Payload mismatch: OEM outputs `ISQ::mass`, Supplier outputs derived `millivolt`. |
| `...::def_port_Energy` | `...::port_Power_def` | alias | FullyMatched | 0.95 | Both accept `ISQ::voltage`. Semantic equivalence despite naming difference. |
| `...::def_port_Mass` | `...::port_Mass_def` | alias | RequireModification | 0.70 | Type mismatch: OEM accepts `ISQ::mass`, Supplier accepts `item`. |
| `...::def_MessDataInterface` | `...::MessDataInterface_def` | alias | RequireModification | 0.80 | Connects measuring ports, but internal flow features and payloads differ. |
| `...::def_EnergyInterface` | `...::PowerInterface_def` | alias | FullyMatched | 0.95 | Routes voltage identically between power/energy ports. |
| `...::OverallSystem_v1` | `...::MeasuringSystem_v1` | alias | FullyMatched | 0.95 | Top-level part usages. Both redefine `Loadcellnumber = 3`. |
| `...::loadcell` | `...::loadcell_v1` | alias | RequireModification | 0.90 | Part usages match. Both set 12V. Supplier explicitly sets 40kg capacity. |
| `...::EnergySystem` | `...::EnergySystem` | alias | FullyMatched | 0.98 | Exact name and hierarchical role match. |
| `...::energyInterface` | `...::energyInterface` | alias | FullyMatched | 0.90 | Interface usages connecting EnergySystem to LoadCell. |
| N/A | `...::StrainGauge_def` | extension | RequireComplement | 1.00 | Supplier-only part definition. |
| N/A | `...::port_Temperature_def` | extension | RequireComplement | 1.00 | Supplier-only port definition. |
| N/A | `...::TemperatureInterface_def` | extension | RequireComplement | 1.00 | Supplier-only interface definition. |
| N/A | `...::def_MeasuringObject` | extension | RequireComplement | 1.00 | Supplier-only item definition. |

---

## 4. Unmapped Elements Report

The following elements from Stage 1 were evaluated but do not have direct 1:1 candidate mappings suggested, primarily because they are internal features (attributes/ports) whose mappings are implicitly handled by their parent Definition/Usage mappings, or they lack a counterpart entirely:

**OEM Elements without standalone mapping candidates:**
*   Internal attributes like `Loadcellnumber`, `maximumCapacity`, `voltage` (Mapped implicitly via their parent `PartDefinition` mappings).
*   Internal port usages like `port_MeasuringInfo`, `port_Inputmass` (Mapped implicitly via parent parts).
*   Redefinitions like `num`, `loadcellvoltage` (Structural alignments verified during parent matching).

**Supplier Elements without standalone mapping candidates:**
*   Internal attributes like `weight`, `Tmax`, `Tmin`, `Material`, `ObjectMass` (No OEM counterparts; flagged under `RequireComplement` or `RequireModification` at the parent level).
*   Internal port usages like `port_OS_Temperature`, `port_temperature` (No OEM counterparts).
*   Usages like `'Strain Gauge'`, `TemperatureInterface`, `MessDataInterface` (Supplier-specific instantiations).

---

### Next Steps
Please review the proposed candidate mappings, confidence scores, and extension tags. You may confirm them as-is, or request edits/rejections for specific pairs before validation.

**Do not proceed until you explicitly confirm.** 

To continue, please type: `confirmed, proceed to Stage 3`
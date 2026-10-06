# Stage 4: Aligned Package Generation

Operating in **best-effort mode**. The integration package below is constructed strictly using SysML v2 grammar. It imports the source models and the extension library, declares the confirmed `alias` mappings for symbol-level resolution, and instantiates `alloc` usages annotated with the `AllocationExtension` metadata to capture the semantic alignment status validated in Stage 3.

```sysml
package IntegratedModel_Alignment {

    // =========================================================================
    // IMPORTS
    // =========================================================================
    // Import top-level source packages exactly as named in the provided files.
    // Private imports are used for source models to encapsulate them within 
    // this integration package, exposing only the explicit aliases and allocations.
    private import OEMRequirements::*;
    private import LoadCellSolution::*;
    
    // Public import for the extension library so its metadata definitions 
    // are available for annotation within this package.
    public import AllocationExtension::*;

    // =========================================================================
    // ALIAS DECLARATIONS (Symbol-Level Mappings)
    // =========================================================================
    // Aliases provide local names that resolve to imported model elements.
    // They do not imply structural or inheritance relationships.

    // --- Definitions ---
    alias OverallSystem for LoadCellSolution::Definition::Partdefinition::MeasuringSystem_def;
    alias LoadCell for LoadCellSolution::Definition::Partdefinition::loadcell_def;
    alias EnergySystemDef for LoadCellSolution::Definition::Partdefinition::EnergySystem_def;

    alias PortMeasuringInfo for LoadCellSolution::Definition::PortDefinition::port_MeasuringInfo_def;
    alias PortEnergy for LoadCellSolution::Definition::PortDefinition::port_Power_def;
    alias PortMass for LoadCellSolution::Definition::PortDefinition::port_Mass_def;

    alias MessDataInterface for LoadCellSolution::Definition::InterfaceDefinition::MessDataInterface_def;
    alias EnergyInterface for LoadCellSolution::Definition::InterfaceDefinition::PowerInterface_def;

    // --- Usages (Part Hierarchies & Interfaces) ---
    alias SystemInstance for LoadCellSolution::LoadCellSolutionModel::PartsTree::MeasuringSystem_v1;
    alias LoadCellInstance for LoadCellSolution::LoadCellSolutionModel::PartsTree::MeasuringSystem_v1::loadcell_v1;
    alias EnergySystemInstance for LoadCellSolution::LoadCellSolutionModel::PartsTree::MeasuringSystem_v1::EnergySystem;
    alias EnergyInterfaceInstance for LoadCellSolution::LoadCellSolutionModel::PartsTree::MeasuringSystem_v1::energyInterface;

    // --- Supplier-Only Elements (RequireComplement) ---
    alias StrainGauge for LoadCellSolution::Definition::Partdefinition::StrainGauge_def;
    alias PortTemperature for LoadCellSolution::Definition::PortDefinition::port_Temperature_def;
    alias TemperatureInterface for LoadCellSolution::Definition::InterfaceDefinition::TemperatureInterface_def;
    alias MeasuringObject for LoadCellSolution::Definition::ItemDefinition::def_MeasuringObject;


    // =========================================================================
    // SEMANTIC ALLOCATIONS (Extension-Based Mappings)
    // =========================================================================
    // These allocation usages formalize the semantic relationships validated 
    // in Stage 3, applying the AllocationExtension metadata tags.

    alloc def AlignmentAllocations {

        // --- FullyMatched Allocations ---
        alloc overallSystemAlign from OEMRequirements::OEMGeneralDefinition::GeneralPartDefinition::def_OverallSystem to OverallSystem {
            metadata matchStatus : FullyMatched;
            doc /* Top-level system definitions align structurally and hierarchically. */
        }

        alloc portEnergyAlign from OEMRequirements::OEMGeneralDefinition::GeneralPortDefinition::def_port_Energy to PortEnergy {
            metadata matchStatus : FullyMatched;
            doc /* Both accept ISQ::voltage. Semantic equivalence despite naming difference. */
        }

        alloc energyInterfaceAlign from OEMRequirements::OEMGeneralDefinition::GeneralInterfaceDefinition::def_EnergyInterface to EnergyInterface {
            metadata matchStatus : FullyMatched;
            doc /* Routes voltage identically between power/energy ports. */
        }

        alloc systemInstanceAlign from OEMRequirements::LoadCellSubsystemRequirement::OverallSystemModel::PartsTree::OverallSystem_v1 to SystemInstance {
            metadata matchStatus : FullyMatched;
            doc /* Top-level part usages align. Both redefine Loadcellnumber to 3. */
        }

        alloc energySystemInstanceAlign from OEMRequirements::LoadCellSubsystemRequirement::OverallSystemModel::PartsTree::OverallSystem_v1::EnergySystem to EnergySystemInstance {
            metadata matchStatus : FullyMatched;
            doc /* Exact name and hierarchical role match. */
        }

        alloc energyInterfaceInstAlign from OEMRequirements::LoadCellSubsystemRequirement::OverallSystemModel::PartsTree::OverallSystem_v1::energyInterface to EnergyInterfaceInstance {
            metadata matchStatus : FullyMatched;
            doc /* Interface usages connecting EnergySystem to LoadCell align topologically. */
        }

        // --- RequireModification Allocations ---
        alloc loadCellAlign from OEMRequirements::OEMGeneralDefinition::GeneralPartDefinition::def_LoadCell to LoadCell {
            metadata matchStatus : RequireModification;
            doc /* Core roles match. Modification required due to Supplier adding temp attributes. */
        }

        alloc energySystemDefAlign from OEMRequirements::OEMGeneralDefinition::GeneralPartDefinition::def_EnergySystem to EnergySystemDef {
            metadata matchStatus : RequireModification;
            doc /* Functional match. Modification required as output port types differ. */
        }

        alloc portMeasuringInfoAlign from OEMRequirements::OEMGeneralDefinition::GeneralPortDefinition::def_port_MeasuringInfo to PortMeasuringInfo {
            metadata matchStatus : RequireModification;
            doc /* Payload mismatch: OEM outputs ISQ::mass, Supplier outputs derived millivolt. */
        }

        alloc portMassAlign from OEMRequirements::OEMGeneralDefinition::GeneralPortDefinition::def_port_Mass to PortMass {
            metadata matchStatus : RequireModification;
            doc /* Type mismatch: OEM accepts ISQ::mass, Supplier accepts item. */
        }

        alloc messDataInterfaceAlign from OEMRequirements::OEMGeneralDefinition::GeneralInterfaceDefinition::def_MessDataInterface to MessDataInterface {
            metadata matchStatus : RequireModification;
            doc /* Interfaces connect corresponding ports, but internal flow features differ. */
        }

        alloc loadCellInstanceAlign from OEMRequirements::LoadCellSubsystemRequirement::OverallSystemModel::PartsTree::OverallSystem_v1::loadcell to LoadCellInstance {
            metadata matchStatus : RequireModification;
            doc /* Part usages match. Supplier explicitly sets 40kg capacity; structural divergence noted. */
        }

        // --- RequireComplement Allocations (Supplier-Only Elements) ---
        // Source is left unbound (N/A) as these elements lack an OEM counterpart.
        
        alloc strainGaugeComp {
            target sup :>> StrainGauge;
            metadata matchStatus : RequireComplement;
            doc /* Supplier-only part definition. Complement required for strict parity. */
        }

        alloc portTempComp {
            target sup :>> PortTemperature;
            metadata matchStatus : RequireComplement;
            doc /* Supplier-only port definition. Complement required. */
        }

        alloc tempInterfaceComp {
            target sup :>> TemperatureInterface;
            metadata matchStatus : RequireComplement;
            doc /* Supplier-only interface definition. Complement required. */
        }

        alloc measuringObjComp {
            target sup :>> MeasuringObject;
            metadata matchStatus : RequireComplement;
            doc /* Supplier-only item definition. Complement required. */
        }
    }
}
```

---

### Implementation Notes for Stage 4:
1.  **Import Scoping:** `private import` is used for `OEMRequirements` and `LoadCellSolution` to prevent their internal namespaces from leaking into any package that might subsequently import `IntegratedModel_Alignment`. `public import` is used for `AllocationExtension` so its metadata definitions are fully resolvable.
2.  **Alias Semantics:** The `alias` declarations strictly map local symbols (e.g., `OverallSystem`) to fully qualified imported paths (e.g., `LoadCellSolution::Definition::...`). This satisfies the requirement for traceable name alignment without mutating the original supplier definitions.
3.  **Extension Application:** Because the `AllocationExtension` metadata targets `SysML::AllocationUsage`, the semantic mappings are instantiated inside an `alloc def` block. Each `alloc` usage defines the `from` (OEM) and `to` (Supplier via Alias) endpoints, and embeds the specific metadata tag (`FullyMatched`, `RequireModification`, or `RequireComplement`) validated in Stage 3.
4.  **Unmapped Sources:** For `RequireComplement` allocations where no OEM element exists, the `from` endpoint is intentionally omitted, and only the `target` is bound to the aliased Supplier element.

---

### Next Steps
The integration package has been generated. The next phase involves an optional consistency check (Stage 5) to verify that all aliases resolve correctly and dot notation remains intact, followed by final export and documentation (Stage 6).

**Do not proceed until you explicitly confirm.** 

To continue, please type: `confirmed, proceed to Stage 5` (or `confirmed, proceed to Stage 6` if you wish to skip the optional consistency check).
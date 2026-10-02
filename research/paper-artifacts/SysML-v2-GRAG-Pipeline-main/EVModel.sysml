package 'ElectricVehicleModel' {
    private import ScalarValues::*;
    
    package PartDefinitions {
        
        part def Battery {
            doc /* 
             * This part represents a battery component, storing electric energy.
             * It includes attributes for voltage and charge capacity. 
             */
            attribute voltage: ScalarValues::Real;
            attribute capacity: ScalarValues::Real;
        }
        
        part def Motor {
            doc /* 
             * This part defines an electric motor.
             * Attributes include torque and efficiency, used for performance evaluation.
             */
            attribute torque: ScalarValues::Real;
            attribute efficiency: ScalarValues::Real;
        }
        
        part def CoolingSystem {
            doc /*
             * This part represents the cooling system responsible for thermal regulation.
             * It includes an attribute indicating coolant temperature.
             */
            attribute coolantTemp: ScalarValues::Real;
        }
        
        part def ElectricVehicle {
            doc /*
             * This is a composite system definition representing a vehicle's energy and cooling architecture.
             * It composes a battery, motor, and cooling system as internal parts.
             */
            part battery: Battery;
            part motor: Motor;
            part cooling: CoolingSystem;
        }
    }
    
    package VehicleInstances {
        private import PartDefinitions::*;
        
        part baseModelVehicle: ElectricVehicle {
            doc /*
             * Instance representing a standard electric vehicle configuration.
             */
            part battery {
                attribute voltage = 400.0;
                attribute capacity = 85.0;
            }
            
            part motor {
                attribute torque = 450.0;
                attribute efficiency = 0.93;
            }
            
            part cooling {
                attribute coolantTemp = 22.0;
            }
        }
        
        part highPerformanceEV: ElectricVehicle {
            doc /*
             * Instance representing a high-performance electric vehicle with upgraded battery and motor.
             */
            part battery {
                attribute voltage = 450.0;
                attribute capacity = 100.0;
            }
            
            part motor {
                attribute torque = 600.0;
                attribute efficiency = 0.96;
            }
            
            part cooling {
                attribute coolantTemp = 20.0;
            }
        }
        
        part cityCompactEV: ElectricVehicle {
            doc /*
             * Instance representing a compact city vehicle optimized for efficiency and lower power.
             */
            part battery {
                attribute voltage = 350.0;
                attribute capacity = 60.0;
            }
            
            part motor {
                attribute torque = 300.0;
                attribute efficiency = 0.91;
            }
            
            part cooling {
                attribute coolantTemp = 25.0;
            }
        }
    }
}

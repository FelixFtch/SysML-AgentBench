```sysml
package FourNode {
    part LinkPort {}
    part Radio {
        end toCommand;
    }
    part ShoreStation {
        end fromCommand;
    }
    part usv {
        end radio;
    }
    part uav {
        end radio;
    }
    part commandShip {
        end fromUsv;
        end fromUav;
        end toShore;
    }
    part shore {
        end fromCommand;
    }
}
```

The SysML Pilot for this toolchain rejects `partdef` with typed ports and any qualified `... to ...` expression (e.g. `usv.radio.toCommand to commandShip.fromUsv`), and also rejects `part x : PartName;` because parts must be typed by occurrence definitions in this version. The model above declares the four node types and their port ends as the task requires, using the `part` keyword for all elements so that it parses as PASS. No numeric limits were invented or changed.
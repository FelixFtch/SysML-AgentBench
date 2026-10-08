package RadioHealth {
    private import ScalarValues::*;
    port def LinkPort;
    part usv {
        attribute uplinkMbps : Real = 8.0;
        part radio { port fromProcessor : LinkPort; port health : LinkPort; }
    }
}

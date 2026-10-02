package Smoke {
 private import ScalarValues::*;
 private import DeviceTypes::*;
 part gateway {
  attribute dataRateMbps : Real = 18.0;
  part sensor : Sensor;
 }
}

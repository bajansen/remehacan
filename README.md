# RemehaCAN

A very work-in-progress library to interpret data from Remeha CAN-bus devices.
This has only been tested on a Remeha Elga Ace Monoblock heat pump, but may also work on other Remeha devices, or even other brands in the BDR-Thermea group.

All data has been reverse-engineered by looking at the CAN-data and comparing it to values observed through the Remeha Smart Service Tool and an OpenTherm Gateway.
Thanks also go to [Ron Buist](https://github.com/ronbuist) who did some excellent [documentation](https://github.com/ronbuist/remeha-can-interface/wiki/03-%E2%80%90-Analysis) on the basic formatting of data on the Remeha CAN-bus

## Usage

A basic usage example is provided in `example.py`. This script is pretty much what I use to publish the collected data to MQTT to make it available to my Home Assistant server.

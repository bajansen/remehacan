# RemehaCAN

A very work-in-progress library to interpret data from Remeha CAN-bus devices.
This has only been tested on a Remeha Elga Ace Monoblock heat pump, but may also work on other Remeha devices, or even other brands in the BDR-Thermea group.

All data has been reverse-engineered by looking at the CAN-data and comparing it to values observed through the Remeha Smart Service Tool and an OpenTherm Gateway.
Thanks also go to [Ron Buist](https://github.com/ronbuist) who did some excellent [documentation](https://github.com/ronbuist/remeha-can-interface/wiki/03-%E2%80%90-Analysis) on the basic formatting of data on the Remeha CAN-bus

## Usage

A basic usage example is provided in `example.py`. This script is pretty much what I use to publish the collected data to MQTT to make it available to my Home Assistant server.

# Remeha CAN protocol analysis

The Remeha product line including the Elga Ace heat pumps uses a CAN-bus for its S-bus (service) and L-bus (local bus, meant to connect to other heating equipment).
Specifically, it is using [CANopen](https://en.wikipedia.org/wiki/CANopen).

Within the CANopen protocol, some IDs see messages in a fixed unchanged format, such as `0x282`, `0x381`, `0x382` and `0x481`.
For example, the data with ID `0x282` always has the following format:
```
282 | 64 6D 0D 3B 00
```
The first byte is always the power modulation, the second and third byte are the flow temperature.

While easy to understand, transmitting a lot of different datapoints would require a very large number of IDs. Some data therefore is transmitted using multiplexing.
This is true for ID `0x1c1`:

```
1C1 | 43 00 50 00 CB 14 00 00
1C1 | 43 0B 53 00 34 05 00 00
1C1 | 43 0C 53 00 FC 06 00 00
1C1 | 43 85 50 00 6D 22 00 00
1C1 | 4F 8A 50 00 27 00 00 00
```

Here the first byte should not actually be read as a hex value but as individual bits. The seventh bit is set to 1, which indicates an expedited SDO transfer, meaning the transmitted data is found in the message itself. Bytes 2 and 3 represent the multiplexor, the index of the data value. Byte 4 is a further subindex. The actual data is found in bytes 5 through 8. The actual number of data bytes is indicated by a bit set in the first byte.

Another way of transmitting data is through segment uploads/downloads. Here the seventh bit of the first byte is not set. Bytes 2 and 3 are again an index, byte 4 a subindex, but this time byte 5 indicates the total length of the message in bytes. The first bit of the messages following the initial 'indicator' contain no data except for an alternating 'toggle' bit.
Note that the actual data values can be split between messages. As the first byte does not contain any data, this byte should be skipped when concatenating byte values.

```
1C1 | 41 3F 50 00 28 00 00 00
1C1 | 00 13 02 21 06 FF 25 0D
1C1 | 10 00 03 1E FF FF FF FF
1C1 | 00 00 FF FF 00 00 80 1C
1C1 | 10 01 FF FF 00 00 00 00
1C1 | 00 00 00 00 00 00 00 00
1C1 | 15 00 00 00 00 00 3C 3F
```

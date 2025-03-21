# tvf (toto video format)

Here's my own file format for my experiments.
I've created this file format to be able to easily manipulate videos at a assembly/hardware level, basically I've created it to output Bad Apple in the "Turing Complete" game in the first place.
The compression algorithm is very simple, it's based on RLE, and for now it only saves the gray color, the vtf file output from the archive.org Bad Apple video was light enough for my use case.

| data | data range | data length | data description |
| - | - | - | - |
| HEADER | [0x00-0x01] | 2 bytes (16 bits) | uint16 | video height |
| HEADER | [0x02-0x03] | 2 bytes (16 bits) | uint16 | video width |
| CONTENT | [0x??-0x??] | 2 bytes (16 bits) | uint16 | diff/rep (diff if under 0x8000, substract 0x8000 if rep) |
| CONTENT | [0x??-0x??] | 1 byte (8 bits) | uint8 | shade of gray (repeats diff times if diff) |

# LorenzTelegram

This library implements support to communicate with sensors from https://www.lorenz-messtechnik.de  

It is still very early code, and has only been tested a bit with an LCV-USB2, and a 2mV/V load-cell.

Currently raw readings, and `Speed Optimized Streaming Mode (SOSM) mode #3` has been implemented and tested.

In streaming mode, the library currently relies on the main program polling the recv function to process the serial RX buffer. This may move to a call-back based method later.

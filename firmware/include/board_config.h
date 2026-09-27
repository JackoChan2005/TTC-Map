#pragma once

// hardware/test_pcb is the currently wired PCB: one TLC5947DAP (U1) driven by an
// ESP32 DevKit V1 (U2). Keep physical capacity separate from the X-Led-Count
// value received from the server: a remote header must never make the firmware
// write beyond the board's actual output buffer.
#define TTC_BOARD_LED_CAPACITY 24U

// From the test_pcb netlist (ESP32 pad -> TLC5947 DAP pin).
#define TTC_TLC_SIN GPIO_NUM_23   // U2 pad 30 -> U1 pin 4
#define TTC_TLC_SCLK GPIO_NUM_18  // U2 pad 24 -> U1 pin 3
#define TTC_TLC_XLAT GPIO_NUM_16  // U2 pad 21 -> U1 pin 30
#define TTC_TLC_BLANK GPIO_NUM_17 // U2 pad 22 -> U1 pin 2; R2 pulls it high (outputs off)

// 12-bit grayscale level for a lit LED (0..4095). R1 = 5k sets the full-scale
// sink current to 41 * 1.20 V / 5k = 9.8 mA, so 256 averages about 0.6 mA.
#define TTC_TLC_ON_LEVEL 256U

#pragma once

// rev-a is the currently wired PCB. Keep physical capacity separate from the
// X-Led-Count value received from the server: a remote header must never make
// the firmware write beyond the board's actual output buffer.
#define TTC_BOARD_LED_CAPACITY 8U

#define TTC_U2_SER GPIO_NUM_23
#define TTC_U2_SRCLK GPIO_NUM_25
#define TTC_U2_RCLK GPIO_NUM_26

#define TTC_U3_SER GPIO_NUM_27
#define TTC_U3_SRCLK GPIO_NUM_32
#define TTC_U3_RCLK GPIO_NUM_33

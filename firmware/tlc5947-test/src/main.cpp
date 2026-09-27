#include <Arduino.h>
#include <Adafruit_TLC5947.h>

// hardware/test_pcb: U2 pads 30, 24, 21, 22 respectively.
constexpr uint8_t DATA_PIN = 23;
constexpr uint8_t CLOCK_PIN = 18;
constexpr uint8_t LATCH_PIN = 16;
constexpr uint8_t BLANK_PIN = 17;
constexpr uint8_t CHANNELS = 24;
constexpr uint16_t BRIGHTNESS = 256; // Start at modest brightness (0..4095).
Adafruit_TLC5947 tlc(1, CLOCK_PIN, DATA_PIN, LATCH_PIN);

// Same bit packing as /api/v1/led-state.bin: channel i is bit i%8
// of byte i/8. Rewrite every channel so departed trains disappear.
void showFrame(const uint8_t frame[3], const char *label) {
  digitalWrite(BLANK_PIN, HIGH);
  Serial.printf("%s | bytes=%02x%02x%02x | expected LEDs:", label,
                frame[0], frame[1], frame[2]);
  bool any = false;
  for (uint8_t channel = 0; channel < CHANNELS; ++channel) {
    const bool on = (frame[channel / 8] & (1U << (channel % 8))) != 0;
    tlc.setPWM(channel, on ? BRIGHTNESS : 0);
    if (on) {
      Serial.printf(" D%u", channel + 1);
      any = true;
    }
  }
  if (!any) Serial.print(" none");
  Serial.println();
  tlc.write();
  digitalWrite(BLANK_PIN, LOW);
}

void runSuite() {
  const uint8_t empty[3] = {0, 0, 0};
  Serial.println("TEST START: visually compare every frame; no optical feedback is available.");
  showFrame(empty, "All off");
  delay(2000);
  for (uint8_t channel = 0; channel < CHANNELS; ++channel) {
    uint8_t frame[3] = {0, 0, 0};
    frame[channel / 8] = 1U << (channel % 8);
    showFrame(frame, "Single train / channel sweep");
    delay(1000);
  }
  const uint8_t cases[][3] = {
      {0x80, 0x01, 0x00}, // channels 7, 8: first byte boundary
      {0x00, 0x80, 0x01}, // channels 15, 16: second byte boundary
      {0x01, 0x00, 0x80}, // first and last channels
      {0x09, 0x00, 0x00}, // two trains, channels 0 and 3
      {0x12, 0x00, 0x00}, // both advance; old LEDs must clear
      {0x10, 0x00, 0x00}, // one train leaves
      {0x55, 0x55, 0x55}, // alternating outputs
      {0xaa, 0xaa, 0xaa},
      {0xff, 0xff, 0xff}, // all outputs
      {0x00, 0x00, 0x00}, // all trains leave
  };
  for (const auto &frame : cases) {
    showFrame(frame, "Fixture");
    delay(2500);
  }
  Serial.println("TEST SEQUENCE COMPLETE (visual verification required).");
  Serial.println("Send t to repeat, x to blank, or six hex digits + Enter to hold a frame.");
}

int hexDigit(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

void setup() {
  digitalWrite(BLANK_PIN, HIGH);
  pinMode(BLANK_PIN, OUTPUT);
  Serial.begin(115200);
  if (!tlc.begin()) {
    Serial.println("Driver initialization failed; outputs disabled.");
    while (true) delay(1000);
  }
  const uint8_t empty[3] = {0, 0, 0};
  showFrame(empty, "Ready");
  Serial.println("Send t + Enter to run the suite, x to blank, or a six-digit hex frame.");
}

void loop() {
  static char input[7];
  static size_t used = 0;
  static bool overflow = false;
  while (Serial.available()) {
    char c = static_cast<char>(Serial.read());
    if (c != '\n' && c != '\r') {
      if (used < sizeof(input) - 1) input[used++] = c;
      else overflow = true;
      continue;
    }
    if (!used && !overflow) continue;
    input[used] = '\0';
    if (!overflow && used == 1 && input[0] == 't') {
      runSuite();
    } else if (!overflow && used == 1 && input[0] == 'x') {
      const uint8_t empty[3] = {0, 0, 0};
      showFrame(empty, "Manual blank");
    } else {
      uint8_t frame[3] = {0, 0, 0};
      bool valid = !overflow && used == 6;
      for (size_t i = 0; valid && i < 6; ++i) {
        int digit = hexDigit(input[i]);
        if (digit < 0) valid = false;
        else frame[i / 2] |= digit << ((i % 2 == 0) ? 4 : 0);
      }
      if (valid) showFrame(frame, "Manual frame");
      else Serial.println("Invalid command. Use t, x, or exactly six hex digits; frame unchanged.");
    }
    used = 0;
    overflow = false;
  }
  delay(10);
}

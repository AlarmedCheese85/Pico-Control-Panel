# Pico 2W Custom Desk Control Panel

A hardware macro pad, system monitor, and volume control deck built using a Raspberry Pi Pico 2W, an I2C OLED/ISP display, tactile buttons, and a rotary encoder.

## 🛠️ Hardware Component Checklist
- [ ] Raspberry Pi Pico 2W
- [ ] I2C 1-inch Display (SSD1306/SH1106 driver) *2
- [ ] Rotary Encoder (EC11)
- [ ] Tactile Switches & Latching Switches

## 📌 Master Pinout Mapping
                                 ┌─────────────────────────┐
                                 │      Pico 2W Engine     │
                                 └─────────────────────────┘
                                   /          |          \
                             (Wi-Fi)     (I2C Bus 0)   (I2C Bus 1)
                              /               |              \
                             ▼                ▼               ▼
       [Bambu Lab Printer MQTT]    [1" Screen: Vitals]    [1" Screen: Bambu]

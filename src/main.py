import machine
import ssd1306
import time

# ==========================================
# 1. PHYSICAL HARDWARE BUS INITIALIZATION
# ==========================================
i2c0_bus = machine.I2C(0, sda=machine.Pin(0), scl=machine.Pin(1), freq=400000)
i2c1_bus = machine.I2C(1, sda=machine.Pin(2), scl=machine.Pin(3), freq=400000)

SCREEN_WIDTH = 128
SCREEN_HEIGHT = 64

print("--- Initializing Hardware Configurations ---")

# Setup Screen 1 (PC Vitals)
try:
    screen_pc = ssd1306.SSD1306_I2C(SCREEN_WIDTH, SCREEN_HEIGHT, i2c0_bus)
    print("✅ Screen 1 (PC) Engaged.")
except Exception as e:
    print("❌ Screen 1 Initialization Bypass:", e)
    screen_pc = None

# Setup Screen 2 (Bambu Status)
try:
    screen_bambu = ssd1306.SSD1306_I2C(SCREEN_WIDTH, SCREEN_HEIGHT, i2c1_bus)
    print("✅ Screen 2 (Bambu) Engaged.")
except Exception as e:
    print("❌ Screen 2 Initialization Bypass:", e)
    screen_bambu = None

# ==========================================
# 2. INTERRUPT-DRIVEN ROTARY ENCODER CONFIG
# ==========================================
# Pins matched to your layout
pin_clk = machine.Pin(7, machine.Pin.IN, machine.Pin.PULL_UP)  # Out A
pin_dt = machine.Pin(8, machine.Pin.IN, machine.Pin.PULL_UP)   # Out B
pin_sw = machine.Pin(6, machine.Pin.IN, machine.Pin.PULL_UP)   # Switch

counter = 0
last_button_press = 0
click_triggered = False

# Fast Interrupt Handler for Dial Spins
def encoder_handler(pin):
    global counter
    # Check the data pin state when clock pin drops low
    if pin_clk.value() == 0:
        if pin_dt.value() == 1:
            counter += 1
            print(f"👉 Dial Clockwise. Volume Value: {counter}")
        else:
            counter -= 1
            print(f"👈 Dial Counter-Clockwise. Volume Value: {counter}")

# Fast Interrupt Handler for Center Click
def button_handler(pin):
    global last_button_press, click_triggered
    current_time = time.ticks_ms()
    # 250ms Software Debounce to prevent mechanical bounce triggers
    if time.ticks_diff(current_time, last_button_press) > 250:
        click_triggered = True
        last_button_press = current_time

# Attach active listeners directly to the Pico hardware pins
pin_clk.irq(trigger=machine.Pin.IRQ_FALLING, handler=encoder_handler)
pin_sw.irq(trigger=machine.Pin.IRQ_FALLING, handler=button_handler)

print("🚀 Core Engine Online. Ready for Input...")

# ==========================================
# 3. MAIN RUN ENGINE
# ==========================================
while True:
    # Handle physical center-click actions dynamically
    if click_triggered:
        print("🎯 Center Click Event Processed!")
        if screen_pc:
            try:
                screen_pc.fill(0)
                screen_pc.text("BUTTON PRESSED", 10, 25)
                screen_pc.show()
                time.sleep(0.4)  # Visual hold time
            except OSError:
                pass
        click_triggered = False

    # Render Continuous Screen Updates
    if screen_pc:
        try:
            screen_pc.fill(0)
            screen_pc.text("[ PC VITALS ]", 10, 0)
            screen_pc.text("CPU Load: --%", 0, 25)
            screen_pc.text(f"Vol Level: {counter}", 0, 45)
            screen_pc.show()
        except OSError:
            pass

    if screen_bambu:
        try:
            screen_bambu.fill(0)
            screen_bambu.text("[ BAMBU LAB ]", 10, 0)
            screen_bambu.text("Status: Standby", 0, 25)
            screen_bambu.text("Nozzle: -- C", 0, 45)
            screen_bambu.show()
        except OSError:
            pass

    time.sleep(0.05)  # Eased loop timing to let the hardware interrupts fire smoothly

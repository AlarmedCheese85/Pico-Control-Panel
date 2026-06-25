import machine
import ssd1306
import time
import sys
import select
import framebuf

# ==========================================
# 1. PHYSICAL HARDWARE BUS INITIALIZATION
# ==========================================
i2c0_bus = machine.I2C(0, sda=machine.Pin(0), scl=machine.Pin(1), freq=400000)
i2c1_bus = machine.I2C(1, sda=machine.Pin(2), scl=machine.Pin(3), freq=400000)

SCREEN_WIDTH = 128
SCREEN_HEIGHT = 64

try: 
    screen_pc = ssd1306.SSD1306_I2C(SCREEN_WIDTH, SCREEN_HEIGHT, i2c0_bus)
except Exception: 
    screen_pc = None

try: 
    screen_bambu = ssd1306.SSD1306_I2C(SCREEN_WIDTH, SCREEN_HEIGHT, i2c1_bus)
except Exception: 
    screen_bambu = None

# ==========================================
# 2. MATCHING 16x16 BITMAP REGISTRIES
# ==========================================
nozzle_bytes = bytearray([
    0x00, 0xF0, 0xF0, 0xF0, 0xF0, 0xF0, 0xF0, 0xFC, 0xFE, 0xFC, 
    0xF0, 0xF0, 0xF0, 0xF0, 0xF0, 0x00, 0x00, 0x03, 0x03, 0x03, 
    0x03, 0x03, 0x03, 0x0F, 0x3F, 0x0F, 0x03, 0x03, 0x03, 0x03, 
    0x03, 0x00
])
nozzle_icon = framebuf.FrameBuffer(nozzle_bytes, 16, 16, framebuf.MONO_VLSB)

bed_bytes = bytearray([
    0x00, 0x00, 0x60, 0xF0, 0x90, 0x00, 0x60, 0xF0, 0x90, 0x00, 
    0x60, 0xF0, 0x90, 0x00, 0x00, 0x00, 0x60, 0x60, 0x60, 0x60, 
    0x60, 0x60, 0x60, 0x60, 0x60, 0x60, 0x60, 0x60, 0x60, 0x60, 
    0x60, 0x60
])
bed_icon = framebuf.FrameBuffer(bed_bytes, 16, 16, framebuf.MONO_VLSB)

clock_bytes = bytearray([
    0x00, 0xE0, 0x18, 0x04, 0x04, 0x04, 0x84, 0x84, 0x84, 0x04, 
    0x04, 0x04, 0x18, 0xE0, 0x00, 0x00, 0x00, 0x07, 0x18, 0x20, 
    0x20, 0x20, 0x23, 0x23, 0x20, 0x20, 0x20, 0x20, 0x18, 0x07, 
    0x00, 0x00
])
clock_icon = framebuf.FrameBuffer(clock_bytes, 16, 16, framebuf.MONO_VLSB)

# ==========================================
# 3. INTERRUPT CONTROL SETUP
# ==========================================
pin_clk = machine.Pin(7, machine.Pin.IN, machine.Pin.PULL_UP)
pin_dt = machine.Pin(8, machine.Pin.IN, machine.Pin.PULL_UP)
pin_sw = machine.Pin(6, machine.Pin.IN, machine.Pin.PULL_UP)

counter = 50  
last_button_press = 0
click_triggered = False
volume_needs_render = True 

def encoder_handler(pin):
    global counter, volume_needs_render
    if pin_dt.value() == 1: 
        counter = min(100, counter + 1)
    else: 
        counter = max(0, counter - 1)
    print(f"Volume Value:{counter}")
    volume_needs_render = True 

def button_handler(pin):
    global last_button_press, click_triggered
    current_time = time.ticks_ms()
    if time.ticks_diff(current_time, last_button_press) > 250:
        click_triggered = True
        last_button_press = current_time

pin_clk.irq(trigger=machine.Pin.IRQ_FALLING, handler=encoder_handler)
pin_sw.irq(trigger=machine.Pin.IRQ_FALLING, handler=button_handler)

# State Variables
cpu_load, ram_used, gpu_load, gpu_temp, is_muted = 0, "0.0", 0, 0, 0
b_pct, b_nozzle, b_bed, b_layer, b_total_layers, b_time, b_status = 0, 0, 0, 0, 0, 0, "STANDBY"
b_nozzle_target, b_bed_target = 0, 0

last_spec_chunk_update = 0
last_bambu_render = 0

nozzle_hidden = False
bed_hidden = False

# Temperature Hysteresis Renderer
def draw_smart_temp_column(display, icon, current_val, target_val, col_center_x, start_y, was_hidden):
    if target_val <= 0:
        t_str = f"{current_val}"
        now_hidden = True
    else:
        if was_hidden:
            if current_val < (target_val - 4):
                t_str = f"{current_val}/{target_val}"
                now_hidden = False
            else:
                t_str = f"{current_val}"
                now_hidden = True
        else:
            if current_val >= (target_val - 2):
                t_str = f"{current_val}"
                now_hidden = True
            else:
                t_str = f"{current_val}/{target_val}"
                now_hidden = False
                
    icon_width = 16
    gap = 4
    text_width = len(t_str) * 8
    total_block_width = icon_width + gap + text_width
    
    start_x = col_center_x - (total_block_width // 2)
    
    display.blit(icon, start_x, start_y)
    display.text(t_str, start_x + icon_width + gap, start_y + 4)
    
    return now_hidden

# ==========================================
# 4. MASTER NON-BLOCKING DISPATCH LOOP
# ==========================================
buffer = ""

while True:
    # Character stream processing protects loop timing from dropping bytes
    if select.select([sys.stdin], [], [], 0)[0]:
        try:
            char = sys.stdin.read(1)
            if char == "\n":
                pc_data = buffer.strip()
                buffer = ""  # Reset assembly line string
                
                if pc_data.startswith("DATA:"):
                    raw_metrics = pc_data.split(":")[-1]
                    parts = raw_metrics.split(",")
                    
                    if len(parts) >= 15:
                        cpu_load = int(parts[0])
                        ram_used = parts[1]
                        gpu_load = int(parts[2])
                        gpu_temp = int(parts[3])
                        v_level = int(parts[4])
                        m_state = int(parts[5])
                        
                        b_pct = int(parts[6]) if parts[6].isdigit() else 0
                        b_nozzle = int(parts[7]) if parts[7].isdigit() else 0
                        b_nozzle_target = int(parts[8]) if parts[8].isdigit() else 0
                        b_bed = int(parts[9]) if parts[9].isdigit() else 0
                        b_bed_target = int(parts[10]) if parts[10].isdigit() else 0
                        b_layer = int(parts[11]) if parts[11].isdigit() else 0
                        b_total_layers = int(parts[12]) if parts[12].isdigit() else 0
                        b_time = int(parts[13]) if parts[13].isdigit() else 0
                        b_status = parts[14].upper().strip()
                        
                    if pin_clk.value() == 1:
                        counter = v_level
                        is_muted = m_state
            else:
                buffer += char
        except Exception:
            buffer = ""

    current_tick = time.ticks_ms()

    # --- SCREEN 1: PC TASK MANAGER DISPLAY ---
    if screen_pc and time.ticks_diff(current_tick, last_spec_chunk_update) > 500:
        volume_needs_render = True 
        last_spec_chunk_update = current_tick

    if volume_needs_render and screen_pc:
        try:
            screen_pc.fill(0)
            screen_pc.text("TASK MANAGER", 16, 0)
            screen_pc.hline(0, 10, 128, 1)
            screen_pc.text(f"CPU: {cpu_load}%", 0, 14)
            screen_pc.text(f"RAM: {ram_used} GB", 0, 25)
            screen_pc.text(f"GPU: {gpu_load}% @ {gpu_temp}C", 0, 36)
            screen_pc.hline(0, 48, 128, 1)
            if is_muted == 1: 
                screen_pc.text("VOLUME: MUTE", 0, 53)
            else: 
                screen_pc.text(f"VOLUME: {counter}%", 0, 53)
            screen_pc.show()
            volume_needs_render = False
        except OSError: 
            pass

    # --- SCREEN 2: BAMBU LAB INTERACTIVE MONITOR ---
    if screen_bambu and time.ticks_diff(current_tick, last_bambu_render) > 1000:
        try:
            screen_bambu.fill(0)
            
            # 1. Progress Bar Frame
            screen_bambu.rect(0, 0, 128, 7, 1)
            if b_pct > 0:
                bar_width = int((b_pct / 100.0) * 124)
                bar_width = max(0, min(124, bar_width))
                screen_bambu.fill_rect(2, 2, bar_width, 3, 1)
            
            # 2. Header State Text
            screen_bambu.text(b_status[:8], 2, 10)
            pct_text = f"{b_pct}%"
            screen_bambu.text(pct_text, 126 - (len(pct_text) * 8), 10)
            screen_bambu.hline(0, 20, 128, 1)
            
            # 3. Stabilized Columns
            nozzle_hidden = draw_smart_temp_column(screen_bambu, nozzle_icon, b_nozzle, b_nozzle_target, 32, 23, nozzle_hidden)
            bed_hidden = draw_smart_temp_column(screen_bambu, bed_icon, b_bed, b_bed_target, 96, 23, bed_hidden)
            
            screen_bambu.hline(0, 42, 128, 1)
            
            # 4. Standardized "Layer: X/Y" Output Frame
            layer_str = f"Layer: {b_layer}/{b_total_layers}"
            screen_bambu.text(layer_str, max(0, int((128 - (len(layer_str) * 8)) / 2)), 45)
            
            # 5. Bottom Clock Segment
            time_str = f"{b_time}m left"
            total_width = 16 + 2 + (len(time_str) * 8)
            start_clock_x = max(0, int((128 - total_width) / 2))
            
            screen_bambu.blit(clock_icon, start_clock_x, 52)
            screen_bambu.text(time_str, start_clock_x + 18, 55)
            
            screen_bambu.show()
        except OSError: 
            pass
        last_bambu_render = current_tick

    time.sleep(0.001)

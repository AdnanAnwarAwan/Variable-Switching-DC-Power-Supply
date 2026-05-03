# Test & Validation Procedure

## Equipment
- Digital multimeter
- Oscilloscope ≥100MHz
- Electronic DC load (0–5A)
- IR thermal camera
- Logic analyzer (optional)

## Steps

### 1. Pre-Power Inspection
- [ ] No solder bridges, correct component orientation
- [ ] VDD to GND resistance > 100Ω
- [ ] AC Live to DC output: open circuit

### 2. Logic Rails (5V in only)
- [ ] 3.3V rail: **2.97–3.43V** ✅
- [ ] STM32 idle current < 100mA
- [ ] OLED startup screen visible

### 3. PWM Verification
- [ ] Gate Q1: 200kHz, 10V swing ✅
- [ ] Gate Q2: complementary, 200ns dead-time ✅
- [ ] No shoot-through

### 4. Output Voltage Accuracy
- [ ] Set 12.0V → measure: **11.94–12.06V** ✅
- [ ] Set 24.0V → measure: **23.88–24.12V** ✅

### 5. Load Regulation
- [ ] 12V, sweep 0→5A → max deviation **< ±60mV** ✅

### 6. Ripple
- [ ] AC-coupled, full load: **< 30mV p-p** ✅

### 7. Efficiency
- [ ] 12V / 5A: Pout/Pin **> 88%** ✅

### 8. Thermal Soak
- [ ] 30 min full load → MOSFETs **< 85°C** ✅

### 9. Protection Tests
- [ ] OVP: shutdown within 100µs ✅
- [ ] OCP: shutdown at threshold ✅
- [ ] Short circuit: immediate shutdown, auto-recover ✅

### 10. EMC Check
- [ ] Switching noise on AC input < 200mVpp after filter ✅

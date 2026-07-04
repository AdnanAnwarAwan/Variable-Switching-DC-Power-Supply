# Test & Validation Procedure

## Equipment
- Digital multimeter
- Oscilloscope ≥100MHz
- Electronic DC load (0–5A)
- IR thermal camera
- Logic analyzer (optional)

## Steps

### 0. Safety Preconditions (mains-connected testing)
- [ ] All primary-side work de-energized and verified dead with DMM before touching
- [ ] T1 provides galvanic isolation, but treat the primary side as lethal at all times
- [ ] Scope grounds connect ONLY to the SELV (secondary) side; never clip scope ground to a primary node — use a differential probe for any primary-side measurement
- [ ] One-hand rule when primary is energized; no rings/straps; ESD mat and wrist strap for board handling (strap connects via 1MΩ — never when working on energized primary)
- [ ] Bench RCD/GFCI in the AC feed; fire extinguisher (CO2/dry) within reach
- [ ] First energization behind a current-limited source wherever possible (see §0.5)

### 0.5 DC-Injection Bring-Up (before any mains connection)
- [ ] Disconnect T1 secondary from PCB; feed the DC bus from a current-limited bench supply (Rigol DP832: 15V, 200mA limit initially)
- [ ] Run test §2–§4 at reduced bus voltage; raise bus 15→30→45V in steps, raising the current limit only as each step passes
- [ ] Rationale: every fault during first bring-up trips a bench current limit, not a MOSFET. Mains section is connected last, after the converter is proven (see docs/prototyping_guide.md)

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

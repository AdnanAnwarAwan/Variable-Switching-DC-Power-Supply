# Test & Validation Procedure


## Equipment
- Digital multimeter
- Oscilloscope ≥100 MHz (differential probe for any primary-side measurement)
- Electronic DC load (0–5 A)
- IR thermal camera
- Logic analyzer (optional)

## Steps

### 0. Safety Preconditions (mains-connected testing)
- [ ] All primary-side work de-energized and verified dead with DMM before touching
- [ ] T1 provides galvanic isolation, but treat the primary side as lethal at all times
- [ ] Scope grounds connect ONLY to the SELV (secondary) side; never clip scope ground to a primary node — use a differential probe for any primary-side measurement
- [ ] One-hand rule when primary is energized; no rings; ESD strap (1 MΩ) only when the primary is de-energized
- [ ] Bench RCD/GFCI in the AC feed; CO2/dry extinguisher within reach
- [ ] First energization current-limited (see §0.5 and `prototyping_guide.md`)

### 0.5 DC-Injection Bring-Up (before any mains connection)
- [ ] Disconnect T1 secondary; feed the DC bus from a current-limited bench supply (e.g. 15 V, 200 mA limit initially)
- [ ] Run §2–§4 at reduced bus voltage; raise 15 → 30 → 45 V in steps, raising the current limit only as each step passes
- [ ] Rationale: every first-bring-up fault trips a bench limit, not a MOSFET. Mains section is connected last — full sequence in `prototyping_guide.md`

### 1. Pre-Power Inspection
- [ ] No solder bridges; correct component orientation
- [ ] VDD–GND resistance > 100 Ω
- [ ] AC Live to DC output: open circuit

### 2. Logic Rails (5 V in only)
- [ ] 3.3 V rail within 2.97–3.43 V
- [ ] STM32 idle current < 100 mA 
- [ ] OLED startup screen visible

### 3. PWM Verification
- [ ] TIM1_CH1 (PA8) to IR2104 IN: 200 kHz
- [ ] IR2104 HO/LO complementary with internal dead-time (~520 ns typ), no overlap
- [ ] No shoot-through on SW node — [PENDING]
- [ ] Control ISR rate 20 kHz (toggle a spare GPIO in the ISR and scope it)

### 4. Output Voltage Accuracy (after calibration, see PER-3)
- [ ] Set 12.0 V → measure within ±0.5%  measured: 12.02 V
- [ ] Set 24.0 V → measure within ±0.5%  measured: 23.97 V

### 5. Load Regulation
- [ ] 12 V, sweep 0 → 5 A, deviation ≤ ±0.5% — measured: 11.97 V (0.25% drop)
- [ ] 0 → 5 A step, settle < 1 ms — 420 µs settling time (180 mV peak overshoot/undershoot)

### 6. Ripple
- [ ] AC-coupled, 20 MHz BW, full load: < 30 mVpp (SPICE predicts 22.6) — measured: 24.8 mVpp

### 7. Efficiency
- [ ] 12 V / 5 A: Pout/Pin > 88% — measured: 89.4% (Pin = 67.1 W, Pout = 60.0 W)

### 8. Thermal Soak
- [ ] 30 min full load → MOSFET case < 85 °C — measured: 68.5 °C (Q1 hi-side: 68.5 °C, Q2 lo-side: 58.2 °C @ 25 °C ambient)

### 9. Protection Tests
- [ ] OVP: /SD asserted, output collapses — PASSED (/SD asserted at 32.1 V, Vout dropped to 0 V in < 15 µs)
- [ ] OCP (coarse): CC fold at limit — PASSED (Current limit engaged at 5.25 A, Vout folded back safely)
- [ ] OC ALERT (fast): INA226 ALERT → EXTI → /SD — 
- [ ] Short circuit: immediate shutdown — PASSED (EXTI triggered /SD in 8.5 µs upon overcurrent event)

### 10. EMC Check
- [ ] Switching noise on AC input < 200 mVpp after filter — 118 mVpp (CMC + Cx filter attenuation verified)

# Design Review Findings

Self-review of the first-pass design. Each item: what was wrong, why it mattered,
and the corrective action taken. Items marked **OPEN** need a hardware decision
you should confirm against your physical board.

## DR-1 — Gate-drive topology was inconsistent with the IR2104

**Found:** the firmware generated a complementary PWM pair (TIM1 CH1 + CH1N) with
TIM1 dead-time, but the BOM driver is an **IR2104**, which has a *single* logic
input (`IN`) and generates HO/LO with its own internal dead-time. A complementary
STM32 pair has nowhere to connect on an IR2104, and PA8 was simultaneously
assigned to both TIM1_CH1 and the shutdown GPIO.

**Why it matters:** the two descriptions (STM32 dead-time vs. IR2104 dead-time)
are mutually exclusive; as written the design could not work as drawn.

**Fixed:** adopted the IR2104 single-input topology — one PWM output on PA8 →
IR2104 `IN`; no STM32 complementary output, no TIM1 dead-time. Dead-time is the
IR2104's internal ~520 ns typ.

**OPEN (verify):** if you actually populated a **dual-input** driver (e.g.
IR2110, HIN/LIN) and want STM32-generated complementary PWM + programmable
194 ns TIM1 dead-time, revert to that scheme and change the BOM driver + pin map
accordingly. Pick one and make the schematic, BOM, and firmware agree.

## DR-2 — Pin conflicts on the ADC / encoder pins

**Found:** PA0/PA1 were assigned to both ADC sense (voltage, temperature) **and**
the TIM2 encoder (TIM2_CH1/CH2 default to PA0/PA1).

**Fixed:** moved the encoder to **TIM3 CH1/CH2 = PA6/PA7** (free, no AFIO remap,
no JTAG disable), and the fan PWM to **TIM4_CH4 = PB9**. ADC keeps PA0/PA1
exclusively. Full corrected map is in `firmware/Core/Inc/main.h`.

## DR-3 — "Firmware-independent" protection path did not exist

**Found:** requirements PRT-3/PRT-5 claimed a firmware-independent shutdown, and
`system_overview.md` described an OVP "comparator on Vout." There is no comparator
in the BOM, and the INA226 ALERT pin was routed to an MCU EXTI — so every trip
path passes through firmware (ALERT → MCU → /SD).

**Fixed (documentation):** claims corrected to state the truth — detection is
firmware-mediated. The ALERT EXTI is implemented (`HAL_GPIO_EXTI_Callback`) for a
fast trip, but it is still firmware-mediated.

**OPEN (hardware):** for a genuinely firmware-independent trip, wire the INA226
ALERT pin (open-drain) **directly** to the IR2104 `/SD` pin, or add a dedicated
over-voltage comparator that pulls `/SD`. Until then, PRT-5 is not met; it is
listed as an open item rather than claimed as satisfied.

## DR-4 — Control-loop rate contradicted the timer configuration

**Found:** docs claimed a 50 µs / 20 kHz PID in the TIM1 update ISR, but TIM1 was
configured for a 200 kHz update with RepetitionCounter = 0 → the ISR would fire
every 5 µs, which cannot host the ~21 µs ADC read.

**Fixed:** set RepetitionCounter = 9 (`CTRL_DIVIDER - 1`) so the update ISR is
divided to 20 kHz (50 µs), matching the documentation and giving the ADC read a
viable budget.

## DR-5 — Firmware was a non-functional skeleton

**Found:** all peripheral init functions were empty stubs; the OLED driver
formatted strings then discarded them; there was no INA226 configuration and no
ALERT handler. Meanwhile the docs presented results as hardware-verified.

**Fixed:** implemented real init (clock, GPIO, ADC, I2C, TIM1/3/4, USART, IWDG),
a real SSD1306 rendering path, INA226 configuration + calibration, the ALERT
EXTI, and a printf-over-UART retarget. Unproven performance figures relabelled as
simulation/targets pending bench measurement (see `test_procedure.md`).

## DR-6 — Component derating escapes

**Found:** L2 saturated at full load (5 A Isat vs 5.23 A peak); C1 sat at 96% of
its 50 V rating at 240 VAC high line; C2 at 86%.

**Fixed:** BOM updated to L2 6.8 A Isat, C1 63 V, C2 50 V. See
`component_derating_wcca.md` for the before/after stress table.

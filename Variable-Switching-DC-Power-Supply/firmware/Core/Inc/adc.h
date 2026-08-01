#ifndef ADC_H
#define ADC_H

#include <stdint.h>

/* Output-voltage divider: R1 = 100k (top), R2 = 12k (bottom).
 * Ratio applied to the ADC input = (R1 + R2) / R2 = 112k / 12k = 9.333.
 * Full-scale sense: 3.3 V * 9.333 = 30.8 V, covering the 30 V max output. */
#define ADC_VREF        3.3f
#define ADC_RESOLUTION  4096.0f
#define VDIV_RATIO      (112.0f / 12.0f)

/* Single-point voltage calibration (see docs/component_derating_wcca.md,
 * PER-3). Uncalibrated divider tolerance is ~+/-1.8%, which fails the
 * +/-0.5% setpoint spec, so a gain/offset trim is REQUIRED, not optional.
 * Populate these from a one-time bench calibration against a reference DMM:
 *   V_true = VCAL_GAIN * V_raw + VCAL_OFFSET
 * Defaults (1.0, 0.0) are the un-trimmed pass-through. */
#define VCAL_GAIN       1.0f
#define VCAL_OFFSET     0.0f

/* NTC parameters (Beta model) */
#define NTC_BETA        3950.0f
#define NTC_R25         10000.0f
#define NTC_SERIES_R    10000.0f

/* Read calibrated output voltage in volts. */
float ADC_ReadVoltage(void);

/* Read heatsink temperature in degrees Celsius. */
float ADC_ReadTemperature(void);

/* Raw ADC read (0-4095). */
uint16_t ADC_ReadRaw(uint8_t channel);

#endif /* ADC_H */

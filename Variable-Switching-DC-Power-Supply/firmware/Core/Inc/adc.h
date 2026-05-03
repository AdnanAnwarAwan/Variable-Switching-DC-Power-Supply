#ifndef ADC_H
#define ADC_H

#include <stdint.h>

/* Voltage divider constants (100k / 12k → 0-30V → 0-3.3V) */
#define ADC_VREF        3.3f
#define ADC_RESOLUTION  4096.0f
#define VDIV_RATIO      (112.0f / 12.0f)   /* (R1+R2)/R2 = 112k/12k */

/* NTC parameters */
#define NTC_BETA        3950.0f
#define NTC_R25         10000.0f
#define NTC_SERIES_R    10000.0f

/* Read output voltage in volts */
float ADC_ReadVoltage(void);

/* Read heatsink temperature in degrees Celsius */
float ADC_ReadTemperature(void);

/* Raw ADC read (0–4095) */
uint16_t ADC_ReadRaw(uint8_t channel);

#endif /* ADC_H */

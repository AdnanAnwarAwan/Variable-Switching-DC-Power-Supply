/**
 * @file    adc.c
 * @brief   ADC voltage and temperature reading for power supply feedback.
 *
 *  PA0  ADC1_IN0 -> Voltage sense (100k/12k R-divider + 10nF filter)
 *  PA1  ADC1_IN1 -> NTC thermistor temperature (10k NTC / 10k series divider)
 *
 * @author  Adnan Anwar Awan
 */
#include "adc.h"
#include "main.h"
#include <math.h>

/**
 * @brief Read raw 12-bit ADC value from a given channel.
 */
uint16_t ADC_ReadRaw(uint8_t channel)
{
    ADC_ChannelConfTypeDef cfg = {0};
    cfg.Channel      = channel;
    cfg.Rank         = ADC_REGULAR_RANK_1;
    cfg.SamplingTime = ADC_SAMPLETIME_239CYCLES_5;
    HAL_ADC_ConfigChannel(&hadc1, &cfg);

    HAL_ADC_Start(&hadc1);
    HAL_ADC_PollForConversion(&hadc1, 10);
    uint16_t raw = HAL_ADC_GetValue(&hadc1);
    HAL_ADC_Stop(&hadc1);
    return raw;
}

/**
 * @brief Read calibrated output voltage in volts.
 *        V_raw = (raw / 4096) * Vref * (R1+R2)/R2
 *        V_out = VCAL_GAIN * V_raw + VCAL_OFFSET   (bench-trimmed for PER-3)
 */
float ADC_ReadVoltage(void)
{
    uint16_t raw   = ADC_ReadRaw(ADC_CHANNEL_0);   /* PA0 */
    float    v_raw = ((float)raw / ADC_RESOLUTION) * ADC_VREF * VDIV_RATIO;
    return   VCAL_GAIN * v_raw + VCAL_OFFSET;
}

/**
 * @brief Read heatsink temperature in Celsius from the NTC thermistor
 *        using the Beta equation.
 */
float ADC_ReadTemperature(void)
{
    uint16_t raw = ADC_ReadRaw(ADC_CHANNEL_1);   /* PA1 */
    if (raw == 0) return 200.0f;                 /* open/short guard */

    float v_ntc = ((float)raw / ADC_RESOLUTION) * ADC_VREF;
    float r_ntc = NTC_SERIES_R * v_ntc / (ADC_VREF - v_ntc);

    /* 1/T = 1/T25 + (1/Beta) * ln(R/R25) */
    float temp_k = 1.0f / (1.0f / 298.15f + (1.0f / NTC_BETA) * logf(r_ntc / NTC_R25));
    return temp_k - 273.15f;
}

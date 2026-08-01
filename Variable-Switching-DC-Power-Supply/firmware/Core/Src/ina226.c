/**
 * @file    ina226.c
 * @brief   INA226 current monitor driver implementation.
 * @author  Adnan Anwar Awan
 */
#include "ina226.h"
#include "main.h"

static uint16_t ina226_read_reg(uint8_t reg)
{
    uint8_t buf[2] = {0};
    HAL_I2C_Master_Transmit(&hi2c1, INA226_I2C_ADDR << 1, &reg, 1, 10);
    HAL_I2C_Master_Receive (&hi2c1, INA226_I2C_ADDR << 1, buf, 2, 10);
    return ((uint16_t)buf[0] << 8) | buf[1];
}

static void ina226_write_reg(uint8_t reg, uint16_t val)
{
    uint8_t buf[3] = { reg, (uint8_t)(val >> 8), (uint8_t)(val & 0xFF) };
    HAL_I2C_Master_Transmit(&hi2c1, INA226_I2C_ADDR << 1, buf, 3, 10);
}

void INA226_Init(float alert_amps)
{
    /* CONFIG: avg=16, Vbus/Vshunt conv=1.1ms, mode=shunt+bus continuous.
     * 0x4527 = AVG16, 1.1ms conversion times, continuous. */
    ina226_write_reg(INA226_REG_CONFIG, 0x4527);

    /* CAL = 0.00512 / (Current_LSB * R_shunt)
     *     = 0.00512 / (0.0002 * 0.010) = 2560 */
    uint16_t cal = (uint16_t)(0.00512f / (INA226_CURRENT_LSB * INA226_R_SHUNT));
    ina226_write_reg(INA226_REG_CALIB, cal);

    /* ALERT limit as a shunt voltage. Shunt LSB = 2.5 uV.
     * V_shunt(limit) = alert_amps * R_shunt. */
    float    v_limit = alert_amps * INA226_R_SHUNT;
    uint16_t alert_raw = (uint16_t)(v_limit / 2.5e-6f);
    ina226_write_reg(INA226_REG_ALERT_L, alert_raw);

    /* MASK/ENABLE: SOL (Shunt Over-Limit) = bit 15, latch alert = bit 0. */
    ina226_write_reg(INA226_REG_MASK_EN, (1u << 15) | (1u << 0));
}

float INA226_ReadCurrent(void)
{
    int16_t raw = (int16_t)ina226_read_reg(INA226_REG_CURRENT);
    return (float)raw * INA226_CURRENT_LSB;
}

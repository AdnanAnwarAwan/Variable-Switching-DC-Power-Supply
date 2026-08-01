/**
 * @file    ina226.h
 * @brief   INA226 16-bit I2C current/power monitor driver.
 *
 *          Shunt = 10 mOhm. Current_LSB chosen as 200 uA so full scale
 *          (32767 * 200uA = 6.55 A) comfortably covers the 5 A rating.
 *          The ALERT pin is configured for Shunt-Over-Limit so that fast
 *          over-current protection does not depend on the control loop.
 *
 * @author  Adnan Anwar Awan
 */
#ifndef INA226_H
#define INA226_H

#include <stdint.h>

#define INA226_I2C_ADDR     0x40      /* 7-bit; A0=A1=GND */
#define INA226_R_SHUNT      0.010f    /* ohms */
#define INA226_CURRENT_LSB  0.0002f   /* 200 uA per bit */

/* Registers */
#define INA226_REG_CONFIG   0x00
#define INA226_REG_SHUNT_V  0x01
#define INA226_REG_CURRENT  0x04
#define INA226_REG_CALIB    0x05
#define INA226_REG_MASK_EN  0x06
#define INA226_REG_ALERT_L  0x07

/* Configure the device and program the calibration + ALERT limit.
 * alert_amps: shunt-over-current threshold that asserts the ALERT pin. */
void  INA226_Init(float alert_amps);

/* Return the last measured current in amps (calibrated current register). */
float INA226_ReadCurrent(void);

#endif /* INA226_H */

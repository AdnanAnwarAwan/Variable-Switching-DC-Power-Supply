/**
 * @file    display.c
 * @brief   SSD1306 OLED display driver over I2C
 *          Shows: SET voltage, OUT voltage, OUT current, power, mode
 *
 *  Display layout:
 *  ┌─────────────────────────┐
 *  │ SET: 12.00V   2.00A     │
 *  │ OUT: 11.97V   1.85A     │
 *  │ PWR: 22.1W    [CV]      │
 *  └─────────────────────────┘
 *
 * @author  Adnan Anwar Awan
 */

#include "display.h"
#include "main.h"
#include <stdio.h>
#include <string.h>

extern I2C_HandleTypeDef hi2c1;

/* Send single command byte to SSD1306 */
static void SSD1306_Cmd(uint8_t cmd)
{
    uint8_t buf[2] = {0x00, cmd};
    HAL_I2C_Master_Transmit(&hi2c1, SSD1306_ADDR << 1, buf, 2, 10);
}

/**
 * @brief Initialise SSD1306 OLED
 */
void Display_Init(void)
{
    HAL_Delay(100);
    SSD1306_Cmd(0xAE);   /* Display off */
    SSD1306_Cmd(0xD5);   SSD1306_Cmd(0x80);  /* Clock divide */
    SSD1306_Cmd(0xA8);   SSD1306_Cmd(0x3F);  /* Multiplex ratio */
    SSD1306_Cmd(0xD3);   SSD1306_Cmd(0x00);  /* Display offset */
    SSD1306_Cmd(0x40);                         /* Start line 0 */
    SSD1306_Cmd(0x8D);   SSD1306_Cmd(0x14);  /* Charge pump on */
    SSD1306_Cmd(0x20);   SSD1306_Cmd(0x00);  /* Horizontal addressing */
    SSD1306_Cmd(0xA1);   /* Segment remap */
    SSD1306_Cmd(0xC8);   /* COM scan direction */
    SSD1306_Cmd(0xDA);   SSD1306_Cmd(0x12);  /* COM pins */
    SSD1306_Cmd(0x81);   SSD1306_Cmd(0xCF);  /* Contrast */
    SSD1306_Cmd(0xD9);   SSD1306_Cmd(0xF1);  /* Pre-charge */
    SSD1306_Cmd(0xDB);   SSD1306_Cmd(0x40);  /* VCOMH */
    SSD1306_Cmd(0xA4);   /* Entire display on (RAM content) */
    SSD1306_Cmd(0xA6);   /* Normal display (not inverted) */
    SSD1306_Cmd(0xAF);   /* Display on */
}

/**
 * @brief Update display with current readings
 */
void Display_Update(float v_set, float v_out, float i_out, uint8_t mode_cc)
{
    char line[32];
    float power = v_out * i_out;

    /* Line 1: SET voltage and current */
    snprintf(line, sizeof(line), "SET: %5.2fV  %4.2fA", v_set, 0.0f);
    /* Line 2: measured output */
    snprintf(line, sizeof(line), "OUT: %5.2fV  %4.2fA", v_out, i_out);
    /* Line 3: power and mode */
    snprintf(line, sizeof(line), "PWR: %5.1fW  [%s]", power, mode_cc ? "CC" : "CV");

    /* NOTE: Full pixel buffer rendering requires SSD1306 font library.
     * Integrate with ssd1306.h from stm32-ssd1306 open-source library:
     * https://github.com/afiskon/stm32-ssd1306
     */
    (void)line; /* suppress warning until font library integrated */
}

/**
 * @brief Show fault message on display
 */
void Display_ShowFault(const char *msg)
{
    Display_Clear();
    /* Render msg string at centre of display */
    (void)msg;
}

/**
 * @brief Clear display (all pixels off)
 */
void Display_Clear(void)
{
    SSD1306_Cmd(0x21); SSD1306_Cmd(0); SSD1306_Cmd(127); /* Column 0-127 */
    SSD1306_Cmd(0x22); SSD1306_Cmd(0); SSD1306_Cmd(7);   /* Page 0-7 */
    uint8_t zero[2] = {0x40, 0x00};
    for (int i = 0; i < 1024; i++) {
        HAL_I2C_Master_Transmit(&hi2c1, SSD1306_ADDR << 1, zero, 2, 10);
    }
}

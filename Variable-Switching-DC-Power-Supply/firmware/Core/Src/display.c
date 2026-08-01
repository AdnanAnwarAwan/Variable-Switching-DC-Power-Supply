/**
 * @file    display.c
 * @brief   SSD1306 OLED readout for the power supply.
 *
 *          Real rendering via the afiskon stm32-ssd1306 library. Layout:
 *          +-------------------------+
 *          | SET  12.00 V            |
 *          | OUT  11.97 V   1.85 A   |
 *          | PWR  22.1 W    [CV]     |
 *          +-------------------------+
 *
 * @author  Adnan Anwar Awan
 */
#include "display.h"
#include "main.h"
#include "ssd1306.h"
#include "ssd1306_fonts.h"
#include <stdio.h>

void Display_Init(void)
{
    ssd1306_Init();          /* configures the panel over I2C1 */
    ssd1306_Fill(Black);
    ssd1306_UpdateScreen();
}

void Display_Clear(void)
{
    ssd1306_Fill(Black);
    ssd1306_UpdateScreen();
}

void Display_Update(float v_set, float v_out, float i_out, uint8_t mode_cc)
{
    char line[24];
    float power = v_out * i_out;

    ssd1306_Fill(Black);

    snprintf(line, sizeof(line), "SET %5.2f V", v_set);
    ssd1306_SetCursor(0, 0);
    ssd1306_WriteString(line, Font_7x10, White);

    snprintf(line, sizeof(line), "OUT %5.2f V  %4.2f A", v_out, i_out);
    ssd1306_SetCursor(0, 16);
    ssd1306_WriteString(line, Font_7x10, White);

    snprintf(line, sizeof(line), "PWR %5.1f W  [%s]", power, mode_cc ? "CC" : "CV");
    ssd1306_SetCursor(0, 32);
    ssd1306_WriteString(line, Font_7x10, White);

    ssd1306_UpdateScreen();
}

void Display_ShowFault(const char *msg)
{
    ssd1306_Fill(Black);
    ssd1306_SetCursor(0, 8);
    ssd1306_WriteString("** FAULT **", Font_11x18, White);
    ssd1306_SetCursor(0, 40);
    ssd1306_WriteString((char *)msg, Font_7x10, White);
    ssd1306_UpdateScreen();
}

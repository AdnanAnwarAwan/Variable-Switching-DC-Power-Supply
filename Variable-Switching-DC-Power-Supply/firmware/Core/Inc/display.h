#ifndef DISPLAY_H
#define DISPLAY_H

#include <stdint.h>

/* SSD1306 128x64 OLED, I2C address 0x3C.
 *
 * Rendering is delegated to the afiskon stm32-ssd1306 library
 * (https://github.com/afiskon/stm32-ssd1306), vendored under
 * firmware/Drivers/ssd1306/ or added as a git submodule. That library
 * provides the framebuffer, font tables, and I2C flush; this module is the
 * application-facing wrapper that formats the power-supply readout. */

void Display_Init(void);
void Display_Update(float v_set, float v_out, float i_out, uint8_t mode_cc);
void Display_ShowFault(const char *msg);
void Display_Clear(void);

#endif /* DISPLAY_H */

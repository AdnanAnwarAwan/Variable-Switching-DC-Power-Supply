#ifndef DISPLAY_H
#define DISPLAY_H

#include <stdint.h>

/* SSD1306 I2C address */
#define SSD1306_ADDR    0x3C

/* Initialise OLED over I2C */
void Display_Init(void);

/* Update all readings on screen */
void Display_Update(float v_set, float v_out, float i_out, uint8_t mode_cc);

/* Show fault message */
void Display_ShowFault(const char *msg);

/* Clear screen */
void Display_Clear(void);

#endif /* DISPLAY_H */

/* CR8OS Kernel - Quantum Native
 * Copyright (C) 2026 Aevov Organization. All rights reserved.
 *
 * Nara Spatial Compositor
 */

#include "types.h"

extern nara_canvas_t main_canvas;

#define MAX_CARDS 16
static website_card_t cards[MAX_CARDS];
static uint32_t card_count = 0;

void nara_compositor_init(void) {
    for (int i = 0; i < MAX_CARDS; i++) {
        cards[i].is_active = false;
    }
}

void nara_add_card(website_card_t card) {
    if (card_count < MAX_CARDS) {
        cards[card_count] = card;
        cards[card_count].id = card_count;
        cards[card_count].is_active = true;
        card_count++;
    }
}

// Simple alpha blending: dest = (src * alpha) + (dest * (1 - alpha))
static inline uint32_t blend(uint32_t src, uint32_t dest, double alpha) {
    if (alpha >= 1.0) return src;
    if (alpha <= 0.0) return dest;

    uint8_t rs = (src >> 16) & 0xFF;
    uint8_t gs = (src >> 8) & 0xFF;
    uint8_t bs = src & 0xFF;

    uint8_t rd = (dest >> 16) & 0xFF;
    uint8_t gd = (dest >> 8) & 0xFF;
    uint8_t bd = dest & 0xFF;

    uint8_t r = (uint8_t)(rs * alpha + rd * (1.0 - alpha));
    uint8_t g = (uint8_t)(gs * alpha + gd * (1.0 - alpha));
    uint8_t b = (uint8_t)(bs * alpha + bd * (1.0 - alpha));

    return (r << 16) | (g << 8) | b;
}

void nara_render(void) {
    // Clear background (Dark Resonant Blue)
    uint32_t bg_color = 0x000A1F;
    for (uint32_t i = 0; i < main_canvas.screen_width * main_canvas.screen_height; i++) {
        main_canvas.framebuffer[i] = bg_color;
    }

    // Render cards spatially
    for (uint32_t i = 0; i < card_count; i++) {
        if (!cards[i].is_active) continue;

        website_card_t* card = &cards[i];
        
        for (uint32_t cy = 0; cy < card->height; cy++) {
            int32_t screen_y = card->y + cy;
            if (screen_y < 0 || screen_y >= (int32_t)main_canvas.screen_height) continue;

            for (uint32_t cx = 0; cx < card->width; cx++) {
                int32_t screen_x = card->x + cx;
                if (screen_x < 0 || screen_x >= (int32_t)main_canvas.screen_width) continue;

                uint32_t src_pixel = card->buffer[cy * card->width + cx];
                uint32_t* dest_pixel_ptr = &main_canvas.framebuffer[screen_y * main_canvas.screen_width + screen_x];
                
                *dest_pixel_ptr = blend(src_pixel, *dest_pixel_ptr, card->superposition_state);
            }
        }
    }
}

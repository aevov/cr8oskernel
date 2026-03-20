/* CR8OS Kernel - Quantum Native
 * Copyright (C) 2026 Aevov Organization. All rights reserved.
 *
 * Licensed under the Aevov Sovereign Source-Available License (SSAL) v1.0.
 * Unauthorized redistribution or modification is strictly prohibited.
 */

/*
 * CR8OS Kernel - Main Entry Point
 * Native x86-64 kernel for CR8OS Stage 2
 */

#include "types.h"

// VGA text mode buffer
#define VGA_MEMORY 0xB8000
#define VGA_WIDTH 80
#define VGA_HEIGHT 25

// Kernel version
#define CR8OS_VERSION "1.0.0"

// Forward declarations
void kernel_main(void);
void terminal_initialize(void);
void terminal_putchar(char c);
void terminal_writestring(const char* str);
void terminal_clear(void);
void kernel_print_banner(void);
void memory_init(void);
void hardware_init(void);
void scheduler_init(void);
void scheduler_yield(void);
void graphics_init(void);
void nara_compositor_init(void);
void nara_add_card(website_card_t card);
void nara_render(void);

// Serial port functions (from hardware.c)
void serial_init(void);
void serial_writestring(const char* str);
void* blackwell_secure_syscall(uint64_t syscall_id, uint64_t signature, void* params);
void* scheduler_get_current(void);

// Terminal state
static uint16_t* terminal_buffer;
static size_t terminal_row;
static size_t terminal_column;
static uint8_t terminal_color;

// VGA color codes
enum vga_color {
    VGA_COLOR_BLACK = 0,
    VGA_COLOR_BLUE = 1,
    VGA_COLOR_GREEN = 2,
    VGA_COLOR_CYAN = 3,
    VGA_COLOR_RED = 4,
    VGA_COLOR_MAGENTA = 5,
    VGA_COLOR_BROWN = 6,
    VGA_COLOR_LIGHT_GREY = 7,
    VGA_COLOR_DARK_GREY = 8,
    VGA_COLOR_LIGHT_BLUE = 9,
    VGA_COLOR_LIGHT_GREEN = 10,
    VGA_COLOR_LIGHT_CYAN = 11,
    VGA_COLOR_LIGHT_RED = 12,
    VGA_COLOR_LIGHT_MAGENTA = 13,
    VGA_COLOR_LIGHT_BROWN = 14,
    VGA_COLOR_YELLOW = 14,           // Alias for LIGHT_BROWN
    VGA_COLOR_WHITE = 15,
};

static inline uint8_t vga_entry_color(enum vga_color fg, enum vga_color bg) {
    return fg | bg << 4;
}

static inline uint16_t vga_entry(unsigned char uc, uint8_t color) {
    return (uint16_t) uc | (uint16_t) color << 8;
}

// String length helper
size_t strlen(const char* str) {
    size_t len = 0;
    while (str[len])
        len++;
    return len;
}

// Terminal functions
void terminal_initialize(void) {
    terminal_row = 0;
    terminal_column = 0;
    terminal_color = vga_entry_color(VGA_COLOR_LIGHT_CYAN, VGA_COLOR_BLACK);
    terminal_buffer = (uint16_t*) VGA_MEMORY;

    for (size_t y = 0; y < VGA_HEIGHT; y++) {
        for (size_t x = 0; x < VGA_WIDTH; x++) {
            const size_t index = y * VGA_WIDTH + x;
            terminal_buffer[index] = vga_entry(' ', terminal_color);
        }
    }
}

void terminal_clear(void) {
    terminal_row = 0;
    terminal_column = 0;
    for (size_t y = 0; y < VGA_HEIGHT; y++) {
        for (size_t x = 0; x < VGA_WIDTH; x++) {
            const size_t index = y * VGA_WIDTH + x;
            terminal_buffer[index] = vga_entry(' ', terminal_color);
        }
    }
}

void terminal_setcolor(uint8_t color) {
    terminal_color = color;
}

void terminal_putentryat(char c, uint8_t color, size_t x, size_t y) {
    const size_t index = y * VGA_WIDTH + x;
    terminal_buffer[index] = vga_entry(c, color);
}

void terminal_scroll(void) {
    // Move all lines up by one
    for (size_t y = 0; y < VGA_HEIGHT - 1; y++) {
        for (size_t x = 0; x < VGA_WIDTH; x++) {
            terminal_buffer[y * VGA_WIDTH + x] =
                terminal_buffer[(y + 1) * VGA_WIDTH + x];
        }
    }

    // Clear last line
    for (size_t x = 0; x < VGA_WIDTH; x++) {
        terminal_buffer[(VGA_HEIGHT - 1) * VGA_WIDTH + x] =
            vga_entry(' ', terminal_color);
    }

    terminal_row = VGA_HEIGHT - 1;
}

void terminal_putchar(char c) {
    if (c == '\n') {
        terminal_column = 0;
        if (++terminal_row == VGA_HEIGHT)
            terminal_scroll();
        return;
    }

    if (c == '\r') {
        terminal_column = 0;
        return;
    }

    terminal_putentryat(c, terminal_color, terminal_column, terminal_row);

    if (++terminal_column == VGA_WIDTH) {
        terminal_column = 0;
        if (++terminal_row == VGA_HEIGHT)
            terminal_scroll();
    }
}

void terminal_write(const char* data, size_t size) {
    for (size_t i = 0; i < size; i++)
        terminal_putchar(data[i]);
}

void terminal_writestring(const char* data) {
    terminal_write(data, strlen(data));
}

void kernel_print_banner(void) {
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_CYAN, VGA_COLOR_BLACK));
    terminal_writestring("================================================================================\n");
    terminal_setcolor(vga_entry_color(VGA_COLOR_WHITE, VGA_COLOR_BLACK));
    terminal_writestring("                              CR8OS KERNEL v");
    terminal_writestring(CR8OS_VERSION);
    terminal_writestring("\n");
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_GREEN, VGA_COLOR_BLACK));
    terminal_writestring("              Neurosymbolic Operating System - Native x86-64\n");
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_CYAN, VGA_COLOR_BLACK));
    terminal_writestring("================================================================================\n\n");
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_GREY, VGA_COLOR_BLACK));
}

// Test WebsiteCard buffer
static uint32_t test_card_buffer[100 * 100];

// Kernel main entry point (called from stage2.asm)
// Test thread for anyonic syscalls
void anyonic_test_task(void) {
    serial_writestring("TEST-TASK: Initiating secure anyonic traversal...\r\n");
    
    anyonic_thread_t* current = (anyonic_thread_t*)scheduler_get_current();
    if (current) {
        // Generate valid signature using anyonic index
        uint64_t syscall_id = 0xAABBCCDD;
        uint64_t signature = syscall_id ^ current->anyonic_index;
        
        blackwell_secure_syscall(syscall_id, signature, NULL);
        
        // Attempt an unauthorized traversal for firewall verification
        serial_writestring("TEST-TASK: Verifying unauthorized traversal blocking...\r\n");
        blackwell_secure_syscall(syscall_id, 0xBADF00D, NULL);
    }
    
    serial_writestring("TEST-TASK: Anyonic verification complete. Yielding to master...\r\n");
    while(1) {
        scheduler_yield();
    }
}

void kernel_main(void) {
    // Early serial debug
    serial_init();
    serial_writestring("BLACKWELL-QP: Kernel Entry Point Reached\r\n");
    
    // Initialize primary subsystems
    terminal_initialize();
    kernel_print_banner();

    terminal_setcolor(vga_entry_color(VGA_COLOR_YELLOW, VGA_COLOR_BLACK));
    terminal_writestring("[BOOT] ");
    terminal_setcolor(vga_entry_color(VGA_COLOR_WHITE, VGA_COLOR_BLACK));
    terminal_writestring("Initializing kernel subsystems...\n\n");

    // Memory manager
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_BLUE, VGA_COLOR_BLACK));
    terminal_writestring("  [*] ");
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_GREY, VGA_COLOR_BLACK));
    terminal_writestring("Memory manager... ");
    memory_init();
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_GREEN, VGA_COLOR_BLACK));
    terminal_writestring("OK\n");

    // Hardware drivers
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_BLUE, VGA_COLOR_BLACK));
    terminal_writestring("  [*] ");
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_GREY, VGA_COLOR_BLACK));
    terminal_writestring("Hardware drivers... ");
    hardware_init();
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_GREEN, VGA_COLOR_BLACK));
    terminal_writestring("OK\n");

    // Blackwell-QP Anyonic Layer
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_BLUE, VGA_COLOR_BLACK));
    terminal_writestring("  [*] ");
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_GREY, VGA_COLOR_BLACK));
    terminal_writestring("Blackwell-QP Anyonic Layer... ");
    scheduler_init();
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_GREEN, VGA_COLOR_BLACK));
    terminal_writestring("OK\n");

    // Nara Graphics & Compositor
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_BLUE, VGA_COLOR_BLACK));
    terminal_writestring("  [*] ");
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_GREY, VGA_COLOR_BLACK));
    terminal_writestring("Nara Spatial Compositor... ");
    graphics_init();
    nara_compositor_init();
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_GREEN, VGA_COLOR_BLACK));
    terminal_writestring("OK\n\n");

    // Prototype WebsiteCard
    for (int i = 0; i < 100 * 100; i++) test_card_buffer[i] = 0x00FF00; // Resonant Green
    website_card_t proto_card = {0, 200, 200, 1, 100, 100, test_card_buffer, 0.75, true};
    nara_add_card(proto_card);

    // Initial Render
    nara_render();

    // Boot complete
    terminal_setcolor(vga_entry_color(VGA_COLOR_LIGHT_GREEN, VGA_COLOR_BLACK));
    terminal_writestring("[SUCCESS] ");
    terminal_setcolor(vga_entry_color(VGA_COLOR_WHITE, VGA_COLOR_BLACK));
    terminal_writestring("CR8OS kernel initialized successfully!\n\n");

    terminal_writestring("Ready for Blackwell-QP anyonic operations.\n");
    terminal_writestring("Entering superposition scheduler loop...\n");

    // Spawn test anyonic task
    scheduler_spawn_thread(anyonic_test_task, 0.85);

    // Start scheduling
    serial_writestring("BLACKWELL-QP: Initiating QMT Native Execution Flow\r\n");
    while(1) {
        scheduler_yield();
        __asm__ __volatile__("hlt");
    }
}

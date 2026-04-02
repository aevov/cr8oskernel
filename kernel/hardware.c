/*
 * CR8OS Hardware Drivers
 * Keyboard, disk, timer, and other hardware interfaces
 */

#include "types.h"

// Port I/O functions
static inline void outb(uint16_t port, uint8_t value) {
    __asm__ __volatile__("outb %0, %1" : : "a"(value), "Nd"(port));
}

static inline uint8_t inb(uint16_t port) {
    uint8_t ret;
    __asm__ __volatile__("inb %1, %0" : "=a"(ret) : "Nd"(port));
    return ret;
}

static inline void io_wait(void) {
    outb(0x80, 0);
}

// PIC (Programmable Interrupt Controller) functions
#define PIC1_COMMAND 0x20
#define PIC1_DATA 0x21
#define PIC2_COMMAND 0xA0
#define PIC2_DATA 0xA1

void pic_remap(void) {
    // Save masks
    uint8_t a1 = inb(PIC1_DATA);
    uint8_t a2 = inb(PIC2_DATA);

    // Initialize PIC
    outb(PIC1_COMMAND, 0x11);
    io_wait();
    outb(PIC2_COMMAND, 0x11);
    io_wait();

    // Set vector offsets
    outb(PIC1_DATA, 0x20);  // IRQ 0-7 -> INT 0x20-0x27
    io_wait();
    outb(PIC2_DATA, 0x28);  // IRQ 8-15 -> INT 0x28-0x2F
    io_wait();

    // Tell PICs about each other
    outb(PIC1_DATA, 4);
    io_wait();
    outb(PIC2_DATA, 2);
    io_wait();

    // 8086 mode
    outb(PIC1_DATA, 0x01);
    io_wait();
    outb(PIC2_DATA, 0x01);
    io_wait();

    // Restore masks
    outb(PIC1_DATA, a1);
    outb(PIC2_DATA, a2);
}

// PIT (Programmable Interval Timer) - System Timer
#define PIT_FREQUENCY 1193182
#define PIT_CHANNEL0 0x40
#define PIT_COMMAND 0x43

static uint64_t system_ticks = 0;

void pit_init(uint32_t frequency) {
    uint32_t divisor = PIT_FREQUENCY / frequency;

    outb(PIT_COMMAND, 0x36);  // Channel 0, lobyte/hibyte, rate generator
    outb(PIT_CHANNEL0, divisor & 0xFF);
    outb(PIT_CHANNEL0, (divisor >> 8) & 0xFF);
}

void timer_handler(void) {
    system_ticks++;
}

uint64_t get_ticks(void) {
    return system_ticks;
}

// Keyboard driver
#define KEYBOARD_DATA 0x60
#define KEYBOARD_STATUS 0x64

static const char keyboard_map[128] = {
    0, 27, '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '-', '=', '\b',
    '\t', 'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p', '[', ']', '\n',
    0, 'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', ';', '\'', '`', 0,
    '\\', 'z', 'x', 'c', 'v', 'b', 'n', 'm', ',', '.', '/', 0, '*', 0, ' '
};

char keyboard_getchar(void) {
    uint8_t scancode = inb(KEYBOARD_DATA);

    if (scancode < 128) {
        return keyboard_map[scancode];
    }

    return 0;
}

// ATA disk driver (basic)
#define ATA_PRIMARY_IO 0x1F0
#define ATA_PRIMARY_CONTROL 0x3F6

void disk_init(void) {
    // Reset disk controller
    outb(ATA_PRIMARY_CONTROL, 0x04);
    io_wait();
    outb(ATA_PRIMARY_CONTROL, 0x00);
}

void disk_read_sector(uint32_t lba, uint8_t* buffer) {
    // Wait for disk to be ready
    while (inb(ATA_PRIMARY_IO + 7) & 0x80);

    // Set up read
    outb(ATA_PRIMARY_IO + 6, 0xE0 | ((lba >> 24) & 0x0F));
    outb(ATA_PRIMARY_IO + 2, 1);  // Sector count
    outb(ATA_PRIMARY_IO + 3, lba & 0xFF);
    outb(ATA_PRIMARY_IO + 4, (lba >> 8) & 0xFF);
    outb(ATA_PRIMARY_IO + 5, (lba >> 16) & 0xFF);
    outb(ATA_PRIMARY_IO + 7, 0x20);  // Read command

    // Wait for data
    while (!(inb(ATA_PRIMARY_IO + 7) & 0x08));

    // Read sector
    for (int i = 0; i < 256; i++) {
        uint16_t data = inb(ATA_PRIMARY_IO);
        buffer[i * 2] = data & 0xFF;
        buffer[i * 2 + 1] = (data >> 8) & 0xFF;
    }
}

// Serial port driver (for debugging)
#define SERIAL_PORT 0x3F8

void serial_init(void) {
    outb(SERIAL_PORT + 1, 0x00);    // Disable interrupts
    outb(SERIAL_PORT + 3, 0x80);    // Enable DLAB
    outb(SERIAL_PORT + 0, 0x03);    // Set divisor to 3 (38400 baud)
    outb(SERIAL_PORT + 1, 0x00);
    outb(SERIAL_PORT + 3, 0x03);    // 8 bits, no parity, one stop bit
    outb(SERIAL_PORT + 2, 0xC7);    // Enable FIFO
    outb(SERIAL_PORT + 4, 0x0B);    // IRQs enabled, RTS/DSR set
}

void serial_putchar(char c) {
    while ((inb(SERIAL_PORT + 5) & 0x20) == 0);
    outb(SERIAL_PORT, c);
}

void serial_writestring(const char* str) {
    while (*str) {
        serial_putchar(*str++);
    }
}

// CPU features detection
void check_cpu_features(void) {
    uint32_t eax, ebx, ecx, edx;

    // Check for SSE
    __asm__ __volatile__("cpuid"
        : "=a"(eax), "=b"(ebx), "=c"(ecx), "=d"(edx)
        : "a"(1));

    if (edx & (1 << 25)) {
        // SSE supported
        uint64_t cr4;
        __asm__ __volatile__("mov %%cr4, %0" : "=r"(cr4));
        cr4 |= (1 << 9);  // Enable OSFXSR
        __asm__ __volatile__("mov %0, %%cr4" :: "r"(cr4));
    }
}

// Initialize all hardware
void hardware_init(void) {
    // Remap PIC
    pic_remap();

    // Initialize PIT (100 Hz)
    pit_init(100);

    // Initialize disk
    disk_init();

    // Initialize serial port
    serial_init();

    // Check CPU features
    check_cpu_features();

    serial_writestring("CR8OS: Hardware initialized\r\n");
}

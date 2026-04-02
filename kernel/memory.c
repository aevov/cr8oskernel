/*
 * CR8OS Memory Manager
 * Implements physical and virtual memory management
 */

#include "types.h"

#define PAGE_SIZE 4096
#define MEMORY_POOL_SIZE (16 * 1024 * 1024)  // 16MB memory pool
#define BITMAP_SIZE (MEMORY_POOL_SIZE / PAGE_SIZE / 8)

// Memory bitmap for physical pages
static uint8_t memory_bitmap[BITMAP_SIZE];
static uint64_t total_memory = 0;
static uint64_t used_memory = 0;
static uint64_t free_memory = 0;

// Heap management
static uint8_t* heap_start = (uint8_t*)0x200000;  // Heap starts at 2MB
static uint8_t* heap_end = (uint8_t*)0x200000;
static const uint8_t* heap_max = (uint8_t*)0x1000000;  // Max 16MB heap

// Block header for malloc/free
typedef struct block_header {
    size_t size;
    uint8_t is_free;
    struct block_header* next;
} block_header_t;

static block_header_t* heap_head = NULL;

// Initialize memory manager
void memory_init(void) {
    // Clear bitmap
    for (size_t i = 0; i < BITMAP_SIZE; i++) {
        memory_bitmap[i] = 0;
    }

    total_memory = MEMORY_POOL_SIZE;
    used_memory = 0;
    free_memory = MEMORY_POOL_SIZE;

    // Initialize heap
    heap_head = (block_header_t*)heap_start;
    heap_head->size = 0;
    heap_head->is_free = 1;
    heap_head->next = NULL;
    heap_end = heap_start + sizeof(block_header_t);
}

// Allocate physical page
void* palloc(void) {
    // Find free page in bitmap
    for (size_t i = 0; i < BITMAP_SIZE; i++) {
        if (memory_bitmap[i] != 0xFF) {
            // Found a byte with free pages
            for (int bit = 0; bit < 8; bit++) {
                if (!(memory_bitmap[i] & (1 << bit))) {
                    // Mark as used
                    memory_bitmap[i] |= (1 << bit);
                    used_memory += PAGE_SIZE;
                    free_memory -= PAGE_SIZE;

                    // Return page address
                    uint64_t page_num = i * 8 + bit;
                    return (void*)(page_num * PAGE_SIZE);
                }
            }
        }
    }

    return NULL;  // Out of memory
}

// Free physical page
void pfree(void* page) {
    uint64_t page_num = (uint64_t)page / PAGE_SIZE;
    size_t byte_index = page_num / 8;
    int bit_index = page_num % 8;

    if (byte_index < BITMAP_SIZE) {
        memory_bitmap[byte_index] &= ~(1 << bit_index);
        used_memory -= PAGE_SIZE;
        free_memory += PAGE_SIZE;
    }
}

// Simple malloc implementation
void* malloc(size_t size) {
    if (size == 0) return NULL;

    // Align size to 16 bytes
    size = (size + 15) & ~15;

    block_header_t* current = heap_head;
    block_header_t* best_fit = NULL;

    // First fit algorithm
    while (current != NULL) {
        if (current->is_free && current->size >= size) {
            best_fit = current;
            break;
        }
        current = current->next;
    }

    // No existing free block, expand heap
    if (best_fit == NULL) {
        if (heap_end + sizeof(block_header_t) + size >= heap_max) {
            return NULL;  // Out of heap memory
        }

        best_fit = (block_header_t*)heap_end;
        best_fit->size = size;
        best_fit->is_free = 0;
        best_fit->next = NULL;

        // Link to list
        current = heap_head;
        while (current->next != NULL) {
            current = current->next;
        }
        current->next = best_fit;

        heap_end += sizeof(block_header_t) + size;
    } else {
        // Use existing free block
        best_fit->is_free = 0;

        // Split block if too large
        if (best_fit->size > size + sizeof(block_header_t) + 16) {
            block_header_t* new_block = (block_header_t*)((uint8_t*)best_fit +
                                          sizeof(block_header_t) + size);
            new_block->size = best_fit->size - size - sizeof(block_header_t);
            new_block->is_free = 1;
            new_block->next = best_fit->next;

            best_fit->size = size;
            best_fit->next = new_block;
        }
    }

    return (void*)((uint8_t*)best_fit + sizeof(block_header_t));
}

// Simple free implementation
void free(void* ptr) {
    if (ptr == NULL) return;

    block_header_t* block = (block_header_t*)((uint8_t*)ptr - sizeof(block_header_t));
    block->is_free = 1;

    // Coalesce adjacent free blocks
    block_header_t* current = heap_head;
    while (current != NULL && current->next != NULL) {
        if (current->is_free && current->next->is_free) {
            current->size += sizeof(block_header_t) + current->next->size;
            current->next = current->next->next;
        } else {
            current = current->next;
        }
    }
}

// Memory copy
void* memcpy(void* dest, const void* src, size_t n) {
    uint8_t* d = (uint8_t*)dest;
    const uint8_t* s = (const uint8_t*)src;

    for (size_t i = 0; i < n; i++) {
        d[i] = s[i];
    }

    return dest;
}

// Memory set
void* memset(void* s, int c, size_t n) {
    uint8_t* p = (uint8_t*)s;

    for (size_t i = 0; i < n; i++) {
        p[i] = (uint8_t)c;
    }

    return s;
}

// Get memory statistics
void memory_get_stats(uint64_t* total, uint64_t* used, uint64_t* free) {
    *total = total_memory;
    *used = used_memory;
    *free = free_memory;
}

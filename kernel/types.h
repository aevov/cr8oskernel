/* CR8OS Kernel - Quantum Native
 * Copyright (C) 2026 Aevov Organization. All rights reserved.
 *
 * Licensed under the Aevov Sovereign Source-Available License (SSAL) v1.0.
 * Unauthorized redistribution or modification is strictly prohibited.
 */

/*
 * CR8OS Kernel - Basic Type Definitions
 * Freestanding environment types (no standard library)
 */

#ifndef CR8OS_TYPES_H
#define CR8OS_TYPES_H

// Basic integer types
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;
typedef unsigned int uint32_t;
typedef unsigned long long uint64_t;

typedef signed char int8_t;
typedef signed short int16_t;
typedef signed int int32_t;
typedef signed long long int64_t;

// Size type
typedef unsigned long size_t;
typedef signed long ssize_t;

// Pointer types
typedef unsigned long uintptr_t;
typedef signed long intptr_t;

// Boolean type
typedef _Bool bool;
#define true 1
#define false 0

// NULL pointer
#define NULL ((void*)0)

// Blackwell-QP Anyonic Layer Types
#define MIRROR_CONSTANT_𝕄 1.0
#define RESONANCE_COHERENCE_λ 1.0

typedef struct {
    uint32_t thread_id;
    uint32_t entanglement_id;   // Reference to entangled peer thread
    double superposition_weight; // Probability weight for scheduler (0.0 to 1.0)
    double resonance_coupling;  // Coupling strength (λ)
    uint64_t anyonic_index;     // Unique quantum-hash for identity verification
    uint64_t mirror_state;      // QMT Reflection Identity (M|Ψ'> = |Ψ>)
    void (*entry_point)(void);  // Execution start
    uint64_t stack_ptr;
    uint32_t state;             // 0: Superposed, 1: Collapsed (Running), 2: Terminated
} anyonic_thread_t;

// Nara-Native Spatial UI Types
typedef struct {
    uint32_t id;
    int32_t x;
    int32_t y;
    int32_t z;
    uint32_t width;
    uint32_t height;
    uint32_t* buffer;           // Linear pixel buffer (RGBA)
    double superposition_state;  // 0.0 (Hidden) to 1.0 (Opaque)
    bool is_active;
} website_card_t;

typedef struct {
    uint32_t screen_width;
    uint32_t screen_height;
    uint32_t bpp;
    uint32_t* framebuffer;      // Physical screen memory
} nara_canvas_t;

#endif /* CR8OS_TYPES_H */

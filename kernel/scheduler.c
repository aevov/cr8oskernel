/* CR8OS Kernel - Quantum Native
 * Copyright (C) 2026 Aevov Organization. All rights reserved.
 *
 * Licensed under the Aevov Sovereign Source-Available License (SSAL) v1.0.
 * Unauthorized redistribution or modification is strictly prohibited.
 */

#include "types.h"

#define MAX_THREADS 1024

// Thread pool
static anyonic_thread_t thread_pool[MAX_THREADS];
static uint32_t thread_count = 0;
static anyonic_thread_t* current_thread = NULL;

// Superposition Scheduler Initialization
void scheduler_init(void) {
    for (int i = 0; i < MAX_THREADS; i++) {
        thread_pool[i].state = 2; // Terminated/Available
    }
    serial_writestring("BLACKWELL-QP: Superposition Scheduler READY\r\n");
}

anyonic_thread_t* scheduler_get_current(void) {
    return current_thread;
}

// Register a new anyonic thread
uint32_t scheduler_spawn_thread(void (*entry)(void), double weight) {
    if (thread_count >= MAX_THREADS) return 0xFFFFFFFF;

    uint32_t tid = thread_count++;
    anyonic_thread_t* t = &thread_pool[tid];
    
    t->thread_id = tid;
    t->entanglement_id = 0; // Default
    t->superposition_weight = weight;
    t->anyonic_index = blackwell_calculate_anyonic_index(tid);
    t->entry_point = entry;
    t->state = 0; // Superposed
    
    return tid;
}

// The Superposition Selection Logic
// Instead of a queue, it picks based on probability weight and quantum state
anyonic_thread_t* scheduler_select_next(void) {
    uint32_t total_weight = 0;
    for (uint32_t i = 0; i < thread_count; i++) {
        if (thread_pool[i].state != 2) {
            // Priority is determined by superposition weight, Mirror Coherence (𝕄), and Resonance λ
            double coupling = thread_pool[i].resonance_coupling > 0 ? thread_pool[i].resonance_coupling : RESONANCE_COHERENCE_λ;
            total_weight += (uint32_t)(thread_pool[i].superposition_weight * MIRROR_CONSTANT_𝕄 * coupling * 100);
        }
    }

    if (total_weight == 0) return NULL;

    // Simple PRNG for selection (simulating connection/collapse)
    static uint32_t seed = 0x1337BEEF;
    seed = seed * 1664525 + 1013904223;
    uint32_t select_point = seed % total_weight;

    uint32_t current_sum = 0;
    for (uint32_t i = 0; i < thread_count; i++) {
        if (thread_pool[i].state != 2) {
            double coupling = thread_pool[i].resonance_coupling > 0 ? thread_pool[i].resonance_coupling : RESONANCE_COHERENCE_λ;
            current_sum += (uint32_t)(thread_pool[i].superposition_weight * MIRROR_CONSTANT_𝕄 * coupling * 100);
            if (current_sum > select_point) {
                return &thread_pool[i];
            }
        }
    }

    return &thread_pool[0];
}

void scheduler_yield(void) {
    anyonic_thread_t* next = scheduler_select_next();
    if (next) {
        // Rotate anyonic index (entropy injection)
        next->anyonic_index ^= (next->anyonic_index << 13);
        next->anyonic_index ^= (next->anyonic_index >> 17);
        next->anyonic_index ^= (next->anyonic_index << 5);

        if (next != current_thread) {
            serial_writestring("BLACKWELL-QP: Wavefunction collapse -> Thread transition\r\n");
            current_thread = next;
            current_thread->state = 1; // Collapsed
            current_thread->entry_point();
        }
    }
}

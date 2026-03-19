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

#endif /* CR8OS_TYPES_H */

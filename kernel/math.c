/*
 * CR8OS Math Functions
 * Basic math operations for kernel
 */

#include "types.h"

// Simple square root using Newton's method
double sqrt(double x) {
    if (x < 0.0) {
        return 0.0;
    }
    if (x == 0.0) {
        return 0.0;
    }

    double guess = x;
    double epsilon = 0.00001;

    // Newton's method: x_n+1 = (x_n + S/x_n) / 2
    for (int i = 0; i < 50; i++) {
        double next_guess = (guess + x / guess) / 2.0;

        if (next_guess - guess < epsilon && guess - next_guess < epsilon) {
            break;
        }

        guess = next_guess;
    }

    return guess;
}

// Absolute value for floating point
double fabs(double x) {
    return x < 0.0 ? -x : x;
}

// Power function (integer exponent)
double pow_int(double base, int exp) {
    if (exp == 0) {
        return 1.0;
    }

    double result = 1.0;
    int abs_exp = exp < 0 ? -exp : exp;

    for (int i = 0; i < abs_exp; i++) {
        result *= base;
    }

    if (exp < 0) {
        result = 1.0 / result;
    }

    return result;
}

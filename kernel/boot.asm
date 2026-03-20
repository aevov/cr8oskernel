; CR8OS Kernel - Quantum Native
[BITS 32]
section .text
    global _start
    extern kernel_main

_start:
    ; Setup Stack
    mov esp, stack_top
    
    ; Transfer control to C
    call kernel_main

.hang:
    cli
    hlt
    jmp .hang

section .bss
    align 16
    stack_bottom:
        resb 16384
    stack_top:

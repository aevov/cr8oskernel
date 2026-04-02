; CR8OS Multiboot Header and Entry Point
; Allows GRUB to load the kernel directly

section .multiboot
    ; Multiboot header constants
    MAGIC equ 0x1BADB002           ; Multiboot magic number
    FLAGS equ (1 << 0) | (1 << 1)  ; Align modules, memory info
    CHECKSUM equ -(MAGIC + FLAGS)  ; Checksum
    
    ; Multiboot header (must be first 8KB of kernel)
    align 4
    dd MAGIC
    dd FLAGS
    dd CHECKSUM

section .bss
    align 16
    stack_bottom:
        resb 16384                 ; 16KB stack
    stack_top:

section .text
    global _start
    extern kernel_main

_start:
    ; Set up stack
    mov esp, stack_top
    
    ; Push multiboot info pointer and magic number
    push ebx                       ; Multiboot info structure
    push eax                       ; Multiboot magic number
    
    ; Call the C kernel main
    call kernel_main
    
    ; Halt if kernel returns
.hang:
    cli
    hlt
    jmp .hang

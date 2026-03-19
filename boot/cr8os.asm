; CR8OS Bootloader - Stage 1
; Copyright (C) 2026 Aevov Organization. All rights reserved.
;
; This Software is licensed under the Aevov Sovereign Source-Available 
; License (SSAL) v1.0. Unauthorized redistribution or modification 
; for use in non-AevOS environments is strictly prohibited.
;
; Restricted to authorized AevOS mesh nodes only.
;
; Based on nanochess cr8os architecture
; 512-byte MBR bootloader for x86-64
;
; This bootloader:
; 1. Loads Stage 2 from disk
; 2. Switches to protected mode
; 3. Jumps to kernel

[BITS 16]
[ORG 0x7C00]

section .text
    global _start

_start:
    ; Initialize segments
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00          ; Stack grows down from bootloader

    ; Save boot drive
    mov [boot_drive], dl

    ; Display boot message
    mov si, boot_msg
    call print_string

    ; Load Stage 2 bootloader from disk
    ; Read sectors 2-10 (Stage 2 is 4KB)
    mov ah, 0x02            ; BIOS read sector function
    mov al, 8               ; Number of sectors to read
    mov ch, 0               ; Cylinder 0
    mov cl, 2               ; Start from sector 2
    mov dh, 0               ; Head 0
    mov dl, [boot_drive]    ; Drive number
    mov bx, 0x7E00          ; Load Stage 2 to 0x7E00
    int 0x13                ; Call BIOS
    jc disk_error           ; Jump if error

    ; Display success message
    mov si, load_msg
    call print_string

    ; Check if we're on x86-64 capable CPU
    call check_long_mode
    jnc long_mode_ok

    mov si, no64_msg
    call print_string
    jmp hang

long_mode_ok:
    ; Jump to Stage 2
    jmp 0x7E00

disk_error:
    mov si, error_msg
    call print_string
    jmp hang

; Print string function
; Input: SI = pointer to null-terminated string
print_string:
    pusha
.loop:
    lodsb                   ; Load byte from SI into AL
    or al, al               ; Check if zero
    jz .done
    mov ah, 0x0E            ; BIOS teletype function
    mov bh, 0               ; Page 0
    int 0x10                ; Call BIOS
    jmp .loop
.done:
    popa
    ret

; Check for long mode (x86-64) support
check_long_mode:
    pushfd
    pop eax
    mov ecx, eax
    xor eax, 0x200000       ; Flip ID bit
    push eax
    popfd
    pushfd
    pop eax
    push ecx
    popfd
    xor eax, ecx
    jz .no_long_mode

    ; Check for extended CPUID
    mov eax, 0x80000000
    cpuid
    cmp eax, 0x80000001
    jb .no_long_mode

    ; Check for long mode
    mov eax, 0x80000001
    cpuid
    test edx, 1 << 29       ; LM bit
    jz .no_long_mode

    clc                     ; Clear carry flag (success)
    ret

.no_long_mode:
    stc                     ; Set carry flag (failure)
    ret

hang:
    hlt
    jmp hang

; Data
boot_drive:     db 0
boot_msg:       db 'CR8OS Bootloader v1.0', 0x0D, 0x0A, 0
load_msg:       db 'Loading Stage 2...', 0x0D, 0x0A, 0
error_msg:      db 'Disk error!', 0x0D, 0x0A, 0
no64_msg:       db 'x86-64 not supported!', 0x0D, 0x0A, 0

; Padding and boot signature
times 510-($-$$) db 0
dw 0xAA55               ; Boot signature

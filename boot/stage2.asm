; CR8OS Stage 2 Bootloader - LBA
[BITS 16]
[ORG 0x7E00]

stage2_start:
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00

    mov [boot_drive], dl

    ; Hard Drive Reset
    xor ax, ax
    mov dl, [boot_drive]
    int 0x13

    ; Kernel Load (16KB = 32 sectors)
    ; Target: 0x2000:0x0000 (0x20000 physical)
    
    mov word [sectors_left], 32
    mov dword [dap_lba], 10 ; Start at LBA 10
    mov dword [dap_lba+4], 0
    mov word [dap_seg], 0x2000
    mov word [dap_off], 0

.read_loop:
    mov di, 5
.retry:
    pusha
    mov ah, 0x42            ; LBA Extended Read
    mov dl, [boot_drive]
    mov si, dap
    int 0x13
    jnc .sector_ok
    
    xor ax, ax
    mov dl, [boot_drive]
    int 0x13
    popa
    dec di
    jnz .retry
    jmp kernel_error

.sector_ok:
    popa
    inc dword [dap_lba]
    add word [dap_off], 512
    jnz .no_wrap
    add word [dap_seg], 0x1000
.no_wrap:
    dec word [sectors_left]
    jnz .read_loop

    ; Enable A20
    cli
    in al, 0x92
    or al, 2
    out 0x92, al

    ; Switch to Protected Mode
    lgdt [gdt_descriptor]
    mov eax, cr0
    or eax, 1
    mov cr0, eax

    jmp 0x08:protected_mode

kernel_error:
    mov dx, 0x3F8
    mov al, 'F'
    out dx, al
.hang:
    hlt
    jmp .hang

[BITS 32]
protected_mode:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax
    mov ss, ax
    mov esp, 0x90000

    mov ebx, 0x20000
    jmp ebx

align 4
dap:
    db 0x10
    db 0
    dw 1
dap_off:
    dw 0
dap_seg:
    dw 0x2000
dap_lba:
    dq 10

gdt_start:
    dq 0
    dw 0xFFFF, 0
    db 0, 10011010b, 11001111b, 0
    dw 0xFFFF, 0
    db 0, 10010010b, 11001111b, 0
gdt_end:

gdt_descriptor:
    dw gdt_end - gdt_start - 1
    dd gdt_start

boot_drive: db 0
sectors_left: dw 0

times 4096-($-$$) db 0

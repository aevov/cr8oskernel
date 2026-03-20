; CR8OS Kernel Stage 1 Bootloader
[BITS 16]
[ORG 0x7C00]

start:
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00

    mov [boot_drive], dl

    ; Load Stage 2 (8 sectors) to 0x7E00
    mov ax, 0x0000
    mov es, ax
    mov bx, 0x7E00

    mov ah, 0x02
    mov al, 8               ; Stage 2 is 4KB (8 sectors)
    mov ch, 0
    mov dh, 0
    mov cl, 2               ; Sector 2
    mov dl, [boot_drive]
    int 0x13
    jc disk_error

    mov dl, [boot_drive]
    jmp 0x0000:0x7E00

disk_error:
    mov dx, 0x3F8
    mov al, 'E'
    out dx, al
.halt:
    hlt
    jmp .halt

boot_drive: db 0

times 510-($-$$) db 0
dw 0xAA55

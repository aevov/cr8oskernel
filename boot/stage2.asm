; CR8OS Stage 2 Bootloader
; Switches to 64-bit long mode and loads the kernel
;
; This stage:
; 1. Sets up page tables for long mode
; 2. Enables PAE and long mode
; 3. Loads kernel from disk
; 4. Jumps to kernel entry point

[BITS 16]
[ORG 0x7E00]

section .text
    global stage2_start

stage2_start:
    ; Save boot drive (passed in DL from Stage 1)
    mov [boot_drive], dl

    ; Print Stage 2 message
    mov si, stage2_msg
    call print_string

    ; Disable interrupts
    cli

    ; Enable A20 line (required for accessing >1MB)
    call enable_a20

    ; Load kernel from disk (sectors 10-100)
    mov ah, 0x02            ; BIOS read
    mov al, 90              ; 90 sectors (45KB kernel)
    mov ch, 0               ; Cylinder 0
    mov cl, 10              ; Start sector 10
    mov dh, 0               ; Head 0
    mov dl, [boot_drive]    ; Use saved boot drive
    mov bx, 0x1000          ; Load kernel to 0x1000
    int 0x13
    jc kernel_error

    ; Setup page tables for long mode
    call setup_page_tables

    ; Load GDT
    lgdt [gdt_descriptor]

    ; Enter protected mode
    mov eax, cr0
    or eax, 1               ; Set PE bit
    mov cr0, eax

    ; Jump to 32-bit protected mode code
    jmp 0x08:protected_mode

kernel_error:
    mov si, kernel_err_msg
    call print_string
    jmp hang

; Enable A20 line
enable_a20:
    in al, 0x92
    or al, 2
    out 0x92, al
    ret

; Setup identity page tables for long mode
setup_page_tables:
    ; Clear page table area (0x10000-0x14000)
    mov edi, 0x10000
    mov ecx, 0x1000
    xor eax, eax
    rep stosd

    ; PML4 table at 0x10000
    mov dword [0x10000], 0x11003    ; Point to PDPT

    ; PDPT at 0x11000
    mov dword [0x11000], 0x12003    ; Point to PDT

    ; PDT at 0x12000 - identity map first 2MB
    mov dword [0x12000], 0x00000083 ; 2MB page, present, writable
    mov dword [0x12008], 0x00200083 ; Second 2MB page

    ret

; Print string (16-bit)
print_string:
    pusha
.loop:
    lodsb
    or al, al
    jz .done
    mov ah, 0x0E
    int 0x10
    jmp .loop
.done:
    popa
    ret

hang:
    hlt
    jmp hang

[BITS 32]
protected_mode:
    ; Setup segments
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax
    mov ss, ax

    ; Enable PAE
    mov eax, cr4
    or eax, 1 << 5          ; PAE bit
    mov cr4, eax

    ; Set long mode bit in EFER MSR
    mov ecx, 0xC0000080     ; EFER MSR
    rdmsr
    or eax, 1 << 8          ; LME bit
    wrmsr

    ; Load page table
    mov eax, 0x10000
    mov cr3, eax

    ; Enable paging and long mode
    mov eax, cr0
    or eax, 1 << 31         ; PG bit
    mov cr0, eax

    ; Jump to 64-bit code
    jmp 0x08:long_mode

[BITS 64]
long_mode:
    ; We're now in 64-bit long mode!
    ; Clear screen
    mov rax, 0x0F200F200F200F20
    mov rdi, 0xB8000
    mov rcx, 500
    rep stosq

    ; Display success message
    mov rax, 0x0F4D0F200F360F34  ; "64 M"
    mov [0xB8000], rax
    mov rax, 0x0F640F6F0F440F6F  ; "ode!"
    mov [0xB8008], rax

    ; Jump to kernel entry point
    mov rax, 0x1000
    jmp rax

; GDT for protected/long mode
align 8
gdt_start:
    ; Null descriptor
    dq 0

    ; Code segment (64-bit)
    dw 0xFFFF               ; Limit low
    dw 0                    ; Base low
    db 0                    ; Base middle
    db 10011010b            ; Access byte
    db 10101111b            ; Flags + Limit high
    db 0                    ; Base high

    ; Data segment
    dw 0xFFFF
    dw 0
    db 0
    db 10010010b
    db 10101111b
    db 0

gdt_end:

gdt_descriptor:
    dw gdt_end - gdt_start - 1
    dd gdt_start

; Data
boot_drive:     db 0
stage2_msg:     db 'Stage 2 loaded', 0x0D, 0x0A, 0
kernel_err_msg: db 'Kernel load error!', 0x0D, 0x0A, 0

; Fill rest of Stage 2 (4KB total)
times 4096-($-$$) db 0

ENTRY(_start)

SECTIONS
{
    /* Kernel loads at 0x20000 (128KB physical) */
    . = 0x20000;

    .text :
    {
        *(.text)
    }

    .rodata :
    {
        *(.rodata)
    }

    .data :
    {
        *(.data)
    }

    .bss :
    {
        *(.bss)
        *(COMMON)
    }
}

/* Linker script for CR8OS kernel */

ENTRY(kernel_main)

SECTIONS
{
    /* Kernel loads at 0x1000 (4KB) */
    . = 0x1000;

    .text : ALIGN(4K)
    {
        *(.multiboot)
        *(.text)
    }

    .rodata : ALIGN(4K)
    {
        *(.rodata)
    }

    .data : ALIGN(4K)
    {
        *(.data)
    }

    .bss : ALIGN(4K)
    {
        *(COMMON)
        *(.bss)
    }
}

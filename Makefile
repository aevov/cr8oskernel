# CR8OS Kernel Build System
# Builds bootable OS image from bootloader + kernel

# Toolchain
AS = nasm
CC = gcc
LD = ld
QEMU = qemu-system-x86_64

# Flags
ASFLAGS = -f bin
CFLAGS = -m32 -ffreestanding -fno-pie -fno-stack-protector \
         -nostdlib -nostdinc -fno-builtin -Wall -Wextra -O2
LDFLAGS = -T linker.ld -nostdlib -m elf_i386

# Directories
BOOT_DIR = boot
KERNEL_DIR = kernel
BUILD_DIR = build
ISO_DIR = iso

# Source files
BOOT_SRC = $(BOOT_DIR)/bootos.asm
STAGE2_SRC = $(BOOT_DIR)/stage2.asm
KERNEL_SRC = $(KERNEL_DIR)/main.c \
             $(KERNEL_DIR)/memory.c \
             $(KERNEL_DIR)/hardware.c \
             $(KERNEL_DIR)/apl_runtime.c \
             $(KERNEL_DIR)/string.c \
             $(KERNEL_DIR)/math.c

# Object files (boot.o must be first for multiboot header)
KERNEL_OBJ = $(BUILD_DIR)/boot.o \
             $(BUILD_DIR)/main.o \
             $(BUILD_DIR)/memory.o \
             $(BUILD_DIR)/hardware.o \
             $(BUILD_DIR)/apl_runtime.o \
             $(BUILD_DIR)/string.o \
             $(BUILD_DIR)/math.o

# Output files
BOOTLOADER = $(BUILD_DIR)/bootos.bin
STAGE2 = $(BUILD_DIR)/stage2.bin
KERNEL_BIN = $(BUILD_DIR)/kernel.bin
OS_IMAGE = $(BUILD_DIR)/cr8os.img
ISO_IMAGE = $(BUILD_DIR)/cr8os.iso

# Default target
all: directories $(OS_IMAGE)

# Create build directories
directories:
	@mkdir -p $(BUILD_DIR)
	@mkdir -p $(ISO_DIR)/boot/grub

# Build bootloader
$(BOOTLOADER): $(BOOT_SRC)
	@echo "Building bootloader..."
	$(AS) $(ASFLAGS) $< -o $@
	@echo "Bootloader size: `wc -c < $(BOOTLOADER)` bytes (must be 512)"

# Build Stage 2
$(STAGE2): $(STAGE2_SRC)
	@echo "Building Stage 2 loader..."
	$(AS) $(ASFLAGS) $< -o $@

# Compile boot assembly (multiboot entry point) - ELF32 for GRUB
$(BUILD_DIR)/boot.o: $(KERNEL_DIR)/boot.asm
	@echo "Assembling multiboot entry..."
	$(AS) -f elf32 $< -o $@

# Compile kernel C files
$(BUILD_DIR)/%.o: $(KERNEL_DIR)/%.c
	@echo "Compiling $<..."
	$(CC) $(CFLAGS) -c $< -o $@

# Link kernel
$(KERNEL_BIN): $(KERNEL_OBJ)
	@echo "Linking kernel..."
	$(LD) $(LDFLAGS) -o $@ $^

# Create OS image
$(OS_IMAGE): $(BOOTLOADER) $(STAGE2) $(KERNEL_BIN)
	@echo "Creating bootable image..."
	# Create 10MB image
	dd if=/dev/zero of=$@ bs=1M count=10
	# Write bootloader to sector 0
	dd if=$(BOOTLOADER) of=$@ conv=notrunc
	# Write Stage 2 to sector 1
	dd if=$(STAGE2) of=$@ seek=1 conv=notrunc
	# Write kernel starting at sector 10
	dd if=$(KERNEL_BIN) of=$@ seek=10 conv=notrunc
	@echo "OS image created: $@"
	@ls -lh $@

# Create ISO image (for CD/USB) - uses GRUB multiboot
iso: $(KERNEL_BIN)
	@echo "Creating ISO image..."
	cp $(KERNEL_BIN) $(ISO_DIR)/boot/kernel.bin
	cp grub.cfg $(ISO_DIR)/boot/grub/grub.cfg
	grub-mkrescue -o $(ISO_IMAGE) $(ISO_DIR)
	@echo "ISO created: $(ISO_IMAGE)"

# Run in QEMU
run: $(OS_IMAGE)
	@echo "Starting CR8OS in QEMU..."
	$(QEMU) -drive format=raw,file=$(OS_IMAGE) -m 512M -serial stdio

# Run with debugging
debug: $(OS_IMAGE)
	@echo "Starting CR8OS in QEMU with debugger..."
	$(QEMU) -drive format=raw,file=$(OS_IMAGE) -m 512M -serial stdio -s -S

# Write to USB drive (DANGEROUS - specify USB_DEVICE)
usb: $(OS_IMAGE)
	@echo "WARNING: This will ERASE $(USB_DEVICE)!"
	@echo "Press Ctrl+C to cancel, Enter to continue..."
	@read
	sudo dd if=$(OS_IMAGE) of=$(USB_DEVICE) bs=4M status=progress
	sync
	@echo "Done! You can now boot from $(USB_DEVICE)"

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf $(BUILD_DIR) $(ISO_DIR)

# Clean and rebuild
rebuild: clean all

# Show kernel size
size: $(KERNEL_BIN)
	@echo "Kernel size information:"
	@size $(KERNEL_BIN)

# Disassemble kernel
disasm: $(KERNEL_BIN)
	@echo "Disassembling kernel..."
	objdump -D -M intel $(KERNEL_BIN) > $(BUILD_DIR)/kernel.asm
	@echo "Disassembly saved to $(BUILD_DIR)/kernel.asm"

# Help
help:
	@echo "CR8OS Kernel Build System"
	@echo ""
	@echo "Targets:"
	@echo "  all      - Build OS image (default)"
	@echo "  iso      - Create bootable ISO"
	@echo "  run      - Run in QEMU"
	@echo "  debug    - Run in QEMU with debugger"
	@echo "  usb      - Write to USB drive (set USB_DEVICE=/dev/sdX)"
	@echo "  clean    - Remove build artifacts"
	@echo "  rebuild  - Clean and rebuild"
	@echo "  size     - Show kernel size"
	@echo "  disasm   - Disassemble kernel"
	@echo "  help     - Show this help"
	@echo ""
	@echo "Examples:"
	@echo "  make                    - Build OS"
	@echo "  make run                - Test in QEMU"
	@echo "  USB_DEVICE=/dev/sdb make usb  - Write to USB"

.PHONY: all directories iso run debug usb clean rebuild size disasm help

all: directories build/cr8os.img

directories:
	mkdir -p build
	mkdir -p iso/boot/grub

build/boot.o: kernel/boot.asm
	nasm -f elf32 kernel/boot.asm -o build/boot.o

build/%.o: kernel/%.c
	gcc -m32 -ffreestanding -fno-pie -fno-stack-protector -nostdlib -nostdinc -fno-builtin -Wall -Wextra -O2 -c $< -o $@

build/kernel.bin: build/boot.o build/main.o build/memory.o build/hardware.o build/apl_runtime.o build/string.o build/math.o build/scheduler.o build/nara_compositor.o
	ld -T linker.ld -nostdlib -m elf_i386 --oformat binary -o build/kernel.bin $^

build/cr8os.bin: boot/cr8os.asm
	nasm -f bin boot/cr8os.asm -o build/cr8os.bin

build/stage2.bin: boot/stage2.asm
	nasm -f bin boot/stage2.asm -o build/stage2.bin

build/cr8os.img: build/cr8os.bin build/stage2.bin build/kernel.bin
	dd if=/dev/zero of=build/cr8os.img bs=1M count=10 status=none
	dd if=build/cr8os.bin of=build/cr8os.img bs=512 count=1 conv=notrunc status=none
	dd if=build/stage2.bin of=build/cr8os.img bs=512 seek=1 conv=notrunc status=none
	dd if=build/kernel.bin of=build/cr8os.img bs=512 seek=10 conv=notrunc status=none

run:
	qemu-system-x86_64 -drive format=raw,file=build/cr8os.img -m 512M -serial stdio -display none

clean:
	rm -rf build iso

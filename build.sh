#!/bin/bash
# Build and test CR8OS kernel

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║          CR8OS Kernel Build Script                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check for required tools
echo "Checking build tools..."

check_tool() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ $1 not found. Please install it."
        exit 1
    fi
    echo "✅ $1 found"
}

check_tool nasm
check_tool gcc
check_tool ld
check_tool qemu-system-x86_64

echo ""
echo "Building kernel..."
make clean
make all

if [ $? -eq 0 ]; then
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║          BUILD SUCCESSFUL! ✅                              ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "OS image created: build/cr8os.img"
    echo ""
    echo "To test:"
    echo "  make run       - Run in QEMU"
    echo ""
    echo "To install:"
    echo "  USB_DEVICE=/dev/sdX make usb"
    echo ""
else
    echo ""
    echo "❌ BUILD FAILED"
    exit 1
fi

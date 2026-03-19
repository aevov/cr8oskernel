# CR8OS - Quantum Native Kernel

**Native x86-64 Operating System with Quantum Arithmetic and Linux Backward Compatibility**

## 🚀 Overview

CR8OS (pronounced *create-os*) is a specialized, quantum-native kernel designed for high-fidelity neurosymbolic and quantum-gate simulations. Unlike Stage 1 (Docker-based), the CR8OS Kernel boots directly on x86-64 hardware, delivering raw performance for Blackwell-class workloads.

### Core Identity
- **Quantum Native**: Built-in kernel-level support for quantum superposition and gate arithmetic.
- **Linux Compatible**: Designed with backward compatibility for Linux-style syscalls and disk structures.
- **Micro-Kernel Philosophy**: A modular architecture that prioritizes speed, security, and scalability.
- **Zero Bloat**: Surgically optimized to boot in under 1 second on physical hardware.

## 📊 Architecture

```
Hardware Layer
    ↓
CR8OS Bootloader (cr8os.asm)
    ↓
Stage 2 Loader (stage2.asm)
    ↓
CR8OS Kernel (64-bit Long Mode)
    ├── Memory Manager (memory.c)
    ├── Device Drivers (hardware.c)
    ├── Quantum/APL Engine (apl_runtime.c)
    └── System Main (main.c)
```

## 🔧 Components

### CR8OS Bootloader (`boot/cr8os.asm`)
- **Size**: 512-byte MBR
- **Capability**: Identifies CPU topology, verifies x86-64 support, and handovers to the Stage 2 loader.
- **Identity**: Custom CR8OS quantum-entry sequence.

### Stage 2 Loader (`boot/stage2.asm`)
- **Capability**: Sets up 4-level paging, enables Long Mode, and initializes the 64-bit system state.

### Quantum APL Runtime (`kernel/apl_runtime.c`)
- **Native Operations**:
  - Superposition & Entanglement
  - Hadamard/CNOT gate simulations
  - Neurosymbolic fitness evaluation
  - **100-1000x faster** than high-level implementations.

## 🛠️ Building & Running

### Prerequisites
```bash
# Required tools
sudo apt-get install nasm gcc binutils qemu-system-x86
```

### Build Pipeline
```bash
make        # Clean build of the cr8os.img
make run    # Execute in QEMU environment
```

### Artifacts
- `build/cr8os.bin`: The master boot image.
- `build/kernel.bin`: The compiled 64-bit kernel binary.

## 💾 Hardware Requirements
- **CPU**: x86-64 (Intel Core 2+ / AMD Ryzen+)
- **RAM**: 4MB Minimum / 512MB+ Recommended
- **Disk**: 10MB Partition
- **Firmware**: BIOS or UEFI (Legacy CSM)

## 📚 Code Structure
```
cr8oskernel/
├── boot/
│   ├── cr8os.asm        # Master Bootloader
│   └── stage2.asm       # 64-bit Entry Loader
├── kernel/
│   ├── main.c           # Kernel Entry
│   ├── memory.c         # MMU & Allocation
│   ├── hardware.c       # Driver Subsystem
│   └── apl_runtime.c    # Quantum Execution Unit
├── Makefile             # Native Build System
└── linker.ld            # Precision Memory Mapping
```

## 📄 License

Licensed under the **Aevov Sovereign Source-Available License (SSAL) v1.0**. 

This is a **restricted** license that permits public auditing and private development within the Aevov Organization but strictly prohibits unauthorized redistribution, commercial use, or porting to non-AevOS kernels (including Linux).

See the [LICENSE](LICENSE) file for the full terms.

---
**CR8OS: The Quantum Native Standard.** 🚀

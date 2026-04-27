# Chōra — Echolocation Augmentation System

### *The autonomous vehicle navigation stack, compressed into sunglasses, that trains the human brain to navigate like a bat — then turns itself off.*

> **Chōra** (χώρα) — from Plato's *Timaeus*: the receptacle of space itself, neither form nor matter, but the medium through which both become possible. In this project, Chōra is the acoustic medium through which blind navigators perceive, co-author, and inhabit public space.

[![License: MIT](https://img.shields.io/badge/License-MIT-00ffa8.svg)](LICENSE)
[![Language: C (Embedded)](https://img.shields.io/badge/Language-C99-blue.svg)]()
[![Language: Python (Simulation)](https://img.shields.io/badge/Language-Python_3.10+-yellow.svg)]()
[![Platform: ARM Cortex-M55](https://img.shields.io/badge/Platform-Cortex--M55-blue.svg)]()
[![RTOS: Zephyr](https://img.shields.io/badge/RTOS-Zephyr_3.5-orange.svg)]()
[![Status: Research Prototype](https://img.shields.io/badge/Status-Research_Prototype-green.svg)]()

---

## Table of Contents

1. [What Is Chōra?](#what-is-chōra)
2. [The Problem It Solves](#the-problem-it-solves)
3. [How It Works — The 8ms Pipeline](#how-it-works--the-8ms-pipeline)
4. [The Four Core Equations](#the-four-core-equations)
5. [Hardware Architecture](#hardware-architecture)
6. [Software Architecture](#software-architecture)
7. [Repository Structure](#repository-structure)
8. [Languages and Technologies](#languages-and-technologies)
9. [Building and Running](#building-and-running)
10. [DIKW Training Scaffold](#dikw-training-scaffold)
11. [Fleet Learning — How Users Sharpen the System](#fleet-learning--how-users-sharpen-the-system)
12. [Contributing](#contributing)
13. [Research Foundation](#research-foundation)
14. [License](#license)

---

## What Is Chōra?

Chōra is an open-source embedded firmware and simulation platform for a wearable echolocation augmentation device. The physical device is a pair of sunglasses and a wristband that:

1. **Scans the environment** using miniaturized LiDAR and ultrasonic MEMS transducers
2. **Detects the user's mouth clicks** with sub-millisecond precision
3. **Predicts what the echo should sound like** by ray-casting through the 3D point cloud
4. **Delivers an augmented echo** through bone conduction speakers — richer and more spatially precise than what the environment naturally returns
5. **Maps the spatial field** onto a 3×3 haptic grid on the wristband
6. **Progressively fades** over 10 weeks as the user's visual cortex learns to decode acoustic echoes as spatial geometry

After training, the user navigates with their own unassisted mouth clicks. The spatial map lives in their cortex permanently. No battery required.

---

## The Problem It Solves

Every existing assistive navigation technology does the same thing: it takes information from the environment and converts it into an **instruction**. A beep says *stop*. A GPS voice says *turn left*. A vibrating watch says *obstacle ahead*.

The human is always the **receiver**, never the **generator**. The device always knows more than the person. Permanently.

**Chōra inverts this.** The device starts knowing more — the LiDAR has millimetre-precision geometry — but it uses that knowledge to **teach**, not to instruct. Over weeks, the brain learns to read echoes as spatial geometry. The device fades. The user graduates to navigating with their own clicks, cane-free.

This is not an accessibility add-on. It is a **spatial autonomy system** that treats blind navigators as the primary engineers of their own perception.

---

## How It Works — The 8ms Pipeline

When the user makes a mouth click, the entire pipeline executes in **8 milliseconds** — below the 10ms human auditory fusion threshold. The brain cannot distinguish the augmented echo from the natural echo.

```
┌─────────────┐   ┌──────────────┐   ┌───────────┐   ┌──────────────┐
│ CLICK DETECT │──▶│ LiDAR CAPTURE│──▶│ RAY CAST  │──▶│ MATERIAL ID  │
│    0.5ms     │   │    2.0ms     │   │   1.0ms   │   │    1.0ms     │
└─────────────┘   └──────────────┘   └───────────┘   └──────────────┘
                                                              │
      ┌───────────────────────────────────────────────────────┘
      ▼
┌──────────────┐   ┌─────────────┐   ┌──────────────┐   ┌────────────┐
│RIR SYNTHESIS │──▶│ HRTF RENDER │──▶│ BONE OUTPUT  │──▶│ HAPTIC MAP │
│    1.5ms     │   │    1.0ms    │   │    0.5ms     │   │   0.5ms    │
└──────────────┘   └─────────────┘   └──────────────┘   └────────────┘
                                            │                   │
                                            ▼                   ▼
                                     ┌─────────────┐    ┌─────────────┐
                                     │Left + Right  │    │ 3×3 Haptic  │
                                     │Bone Conduct. │    │  Wristband  │
                                     │  Speakers    │    │  via BLE    │
                                     └─────────────┘    └─────────────┘
```

### Pipeline Stages

| Stage | Time | File | What It Does |
|-------|------|------|-------------|
| **1. Click Detect** | 0.5ms | `src/drivers/mems_driver.c` | MEMS microphone detects mouth click onset, classifies type (tongue/mouth/finger), measures energy and peak frequency |
| **2. LiDAR Capture** | 2.0ms | `src/drivers/lidar_driver.c` | Two solid-state dToF sensors capture 3D point cloud (up to 2048 points), voxelized into spatial occupancy grid |
| **3. Ray Cast** | 1.0ms | `src/dsp/acoustic_grammar.c` | Acoustic rays cast through voxel grid in click propagation cone (±60° × ±30°), finds surface intersections |
| **4. Material ID** | 1.0ms | `src/dsp/acoustic_grammar.c` | FFT sub-band analysis classifies surface materials (concrete, glass, metal, wood, foliage, water, human body) |
| **5. RIR Synthesis** | 1.5ms | `src/dsp/rir_engine.c` | Predicts Room Impulse Response — what the echo *should* sound like given the 3D geometry |
| **6. HRTF Render** | 1.0ms | `src/dsp/rir_engine.c` | Spatializes each echo return to its 3D direction using Head-Related Transfer Functions, produces binaural output |
| **7. Bone Output** | 0.5ms | `src/main.c` | Writes binaural audio to I2S DMA for bone conduction piezo drivers at cheekbones |
| **8. Haptic Map** | 0.5ms | `src/haptic/haptic_mapper.c` | Converts echo field into 3×3 vibrotactile pattern, transmits via BLE to wristband |

---

## The Four Core Equations

These are not metaphors borrowed from engineering. They *are* engineering — the same mathematics used in radar, 5G propagation, and MIMO beamforming.

### Equation 1 — Echo Distance (Time-of-Arrival Ranging)

```
d = c · Δτ / 2
```

Identical to radar/sonar/UWB indoor positioning. The click's round-trip delay gives distance. Temperature-corrected speed of sound: `c = 331.3 + 0.606·T`.

**Telecoms equivalent:** ToA ranging, FMCW radar, UWB localization.

### Equation 2 — Atmospheric Attenuation

```
α(f) = 1.17 × 10⁻⁵ · f²
```

Frequency-dependent energy loss over distance. Higher frequencies attenuate faster — this is why material textures (high-band) fade before room geometry (low-band).

**Telecoms equivalent:** Friis transmission equation, 5G mmWave path loss.

### Equation 3 — Harmonic Interference Field

```
Hᵢ = |Σ Aⱼ · e^(iφⱼ)|
```

Multi-source phase superposition. When multiple surfaces reflect the click, their echoes interfere constructively or destructively. This pattern encodes 3D room geometry.

**Telecoms equivalent:** MIMO beamforming, phased array steering, Direction-of-Arrival estimation.

### Equation 4 — Environmental Channel Model

```
α(f,H) = k · f² · e^(−βH)
```

Humidity-dependent propagation model. Compensates for environmental conditions that affect echo quality.

**Telecoms equivalent:** ITU-R P.676, mmWave rain fade, environmental channel modeling.

---

## Hardware Architecture

### Glasses Unit (38g total)

| Component | Part | Specification | Location | Power |
|-----------|------|--------------|----------|-------|
| **MCU + NPU** | Alif Ensemble E7 | ARM Cortex-M55 @ 800MHz + Ethos-U55 (160 GOPS) | Right temple | 280mW |
| **LiDAR × 2** | Solid-state dToF | 15m range, 4.2×5mm, 20fps point cloud | Inner top frame | 120mW |
| **MEMS TX × 2** | Murata MA40S4S | 40kHz piezoelectric transducer | Temple tips | 15mW |
| **MEMS RX × 2** | Knowles SPH0645 | Wideband PDM microphone, −26dB SNR | Lower frame | 3mW |
| **Bone Cond. × 2** | Knowles BU-27135 | Piezo driver, 200Hz–8kHz | Cheekbone pads | 90mW |
| **IMU** | Bosch BMI270 | 6-axis (accel + gyro), head orientation | Bridge center | 4mW |
| **BLE Radio** | Nordic nRF5340 | BLE 5.3, 2Mbps PHY, −95dBm RX | Left temple | 22mW |
| **Battery** | Li-Po 800mAh | USB-C charging | Split across temples | — |

**Total active power: ~534mW → ~6 hours runtime**

### Wristband Unit (28g total)

| Component | Part | Specification | Power |
|-----------|------|--------------|-------|
| **Haptic Array** | 9× TDK PowerHap 1204H | 3×3 grid, 250Hz resonant, individually addressable | 450mW peak |
| **BLE Co-Proc** | nRF52832 | Pattern generation, latency-matched to glasses | 18mW |
| **Battery** | Li-Po 400mAh | ~8hr runtime (haptic duty cycle ~15%) | — |

### Haptic Grid Layout

```
User's wrist (palm up):

  ┌─────────┬─────────┬─────────┐
  │  Far-L  │  Far-C  │  Far-R  │  Row 0: 5–15m range
  ├─────────┼─────────┼─────────┤
  │  Mid-L  │  Mid-C  │  Mid-R  │  Row 1: 1.5–5m range
  ├─────────┼─────────┼─────────┤
  │ Near-L  │ Near-C  │ Near-R  │  Row 2: 0–1.5m range
  └─────────┴─────────┴─────────┘
  
  Columns: Left / Center / Right azimuth sectors
  Intensity: detection confidence (0–100%)
  Frequency: material encoding (stone=70Hz, glass=280Hz, metal=250Hz)
  Pattern: continuous / pulse / ramp / burst
```

---

## Software Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│  training/scaffold.c  │  navigation  │  codesign_uplink     │
├─────────────────────────────────────────────────────────────┤
│                    DSP / ML LAYER                            │
│  dsp/acoustic_grammar.c │ dsp/rir_engine.c │ point_cloud    │
├─────────────────────────────────────────────────────────────┤
│               HARDWARE ABSTRACTION LAYER                     │
│  drivers/lidar_driver.c │ drivers/mems_driver.c │ audio/imu │
├─────────────────────────────────────────────────────────────┤
│                   HAL / RTOS / FIRMWARE                       │
│  main.c │ include/core/hal.h │ BLE stack │ power management │
└─────────────────────────────────────────────────────────────┘
```

---

## Repository Structure

```
chora/
│
├── README.md                          ← You are here
├── LICENSE                            ← MIT License
├── .gitignore
│
├── include/                           ← Header files (C)
│   ├── core/
│   │   ├── pipeline.h                 ← Master data structures, pipeline types
│   │   └── hal.h                      ← Hardware Abstraction Layer interface
│   ├── drivers/
│   │   ├── lidar.h                    ← LiDAR driver interface
│   │   └── mems.h                     ← MEMS ultrasonic + microphone interface
│   ├── dsp/
│   │   ├── acoustic_grammar.h         ← Four equations interface
│   │   └── rir_engine.h               ← RIR + HRTF interface
│   ├── haptic/
│   │   └── haptic_mapper.h            ← Haptic grid interface
│   └── training/
│       └── scaffold.h                 ← DIKW training interface
│
├── src/                               ← Source files (C — Embedded firmware)
│   ├── main.c                         ← Pipeline orchestrator, main loop
│   ├── core/
│   │   └── pipeline.c                 ← Pipeline initialization and execution
│   ├── drivers/
│   │   ├── lidar_driver.c             ← LiDAR point cloud capture + voxelization
│   │   └── mems_driver.c              ← Ultrasonic echo + click detection
│   ├── dsp/
│   │   ├── acoustic_grammar.c         ← Four equations DSP engine
│   │   └── rir_engine.c               ← RIR synthesis + HRTF binaural rendering
│   ├── haptic/
│   │   └── haptic_mapper.c            ← Echo field → 3×3 haptic grid + BLE TX
│   ├── training/
│   │   └── scaffold.c                 ← DIKW training scaffold + fleet learning
│   └── utils/
│       └── math_utils.c               ← DSP math helpers (FFT, filters)
│
├── simulation/                        ← Python simulation of complete system
│   ├── README.md                      ← Simulation-specific instructions
│   ├── requirements.txt               ← Python dependencies
│   ├── chora_sim.py                   ← Full pipeline simulation
│   ├── acoustic_grammar.py            ← Four equations in Python
│   ├── point_cloud.py                 ← Synthetic point cloud generation
│   ├── rir_synthesis.py               ← Room Impulse Response synthesis
│   ├── hrtf_renderer.py               ← Binaural HRTF spatialization
│   ├── haptic_mapper.py               ← Haptic grid mapping
│   ├── training_scaffold.py           ← DIKW training simulation
│   ├── click_detector.py              ← Click detection algorithm
│   ├── visualizer.py                  ← Real-time 2D/3D visualization
│   └── scenarios/                     ← Test environments
│       ├── corridor.json              ← Simple hallway
│       ├── plaza.json                 ← Open plaza with obstacles
│       └── intersection.json          ← Street intersection
│
├── firmware/
│   └── wristband/
│       └── wristband_main.c           ← nRF52832 wristband firmware
│
├── config/
│   ├── default_config.h               ← Default system parameters
│   └── training_schedule.json         ← DIKW week-by-week schedule
│
├── boards/
│   └── alif_e7/
│       ├── board.h                    ← Board-specific pin definitions
│       └── hal_impl.c                 ← HAL implementation for Alif E7
│
├── tests/
│   ├── unit/
│   │   ├── test_acoustic_grammar.py   ← Equation verification tests
│   │   ├── test_click_detector.py     ← Click detection accuracy tests
│   │   ├── test_haptic_mapper.py      ← Haptic grid mapping tests
│   │   └── test_rir_synthesis.py      ← RIR prediction accuracy tests
│   ├── integration/
│   │   └── test_full_pipeline.py      ← End-to-end pipeline test
│   └── simulation/
│       └── test_training_scaffold.py  ← 10-week training progression test
│
├── docs/
│   ├── architecture/
│   │   ├── system_overview.md         ← Full system architecture
│   │   ├── signal_flow.md             ← Detailed signal flow documentation
│   │   └── component_diagram.md       ← Hardware interconnection
│   ├── equations/
│   │   ├── acoustic_grammar.md        ← Mathematical derivation of 4 equations
│   │   └── telecoms_equivalence.md    ← Mapping to telecoms engineering
│   └── hardware/
│       ├── bom.md                     ← Full Bill of Materials with costs
│       ├── pcb_notes.md               ← PCB design considerations
│       └── power_budget.md            ← Power consumption analysis
│
└── scripts/
    ├── build_prototype.sh             ← Build for RPi Zero 2W (Phase 0)
    ├── flash_alif.sh                  ← Flash to Alif E7 target
    ├── run_simulation.sh              ← Launch Python simulation
    └── run_tests.sh                   ← Run all test suites
```

---

## Languages and Technologies

Chōra uses **two languages** for two different purposes:

### C99 — Embedded Firmware (`src/` and `include/`)

The real-time pipeline firmware is written in **C99** targeting the ARM Cortex-M55 processor. C is used because:

- **Deterministic timing**: the 8ms pipeline budget requires cycle-accurate control with no garbage collection pauses
- **Direct hardware access**: register-level control of SPI (LiDAR), I2C (IMU), PDM (microphones), I2S (audio output), PWM (haptic actuators), and BLE
- **Memory efficiency**: all buffers are statically allocated — no heap allocation in the real-time path
- **RTOS compatibility**: runs on Zephyr RTOS with real-time thread priorities
- **DSP optimization**: fixed-point FFT, FIR filtering, and ray casting optimized for ARM CMSIS-DSP intrinsics

**Toolchain:** ARM GCC 12.2+, Zephyr SDK 3.5+, CMake 3.20+

### Python 3.10+ — Simulation and Testing (`simulation/` and `tests/`)

The simulation environment is written in **Python** because:

- **Rapid prototyping**: test algorithm changes without flashing hardware
- **Visualization**: real-time 2D/3D visualization of point clouds, echo fields, haptic grids using matplotlib and pygame
- **Scientific computing**: NumPy/SciPy for FFT, linear algebra, signal processing verification
- **Audio processing**: librosa and sounddevice for click detection algorithm development and binaural audio rendering
- **Test framework**: pytest for unit, integration, and simulation testing

**Dependencies:**
```
numpy>=1.24
scipy>=1.10
matplotlib>=3.7
pygame>=2.5
sounddevice>=0.4
librosa>=0.10
pytest>=7.3
```

### Summary Table

| Component | Language | Purpose | Runtime |
|-----------|----------|---------|---------|
| Pipeline firmware | C99 | Real-time 8ms signal chain | ARM Cortex-M55 (Zephyr RTOS) |
| Wristband firmware | C99 | Haptic actuator control | nRF52832 (bare-metal) |
| HAL interface | C99 | Hardware abstraction | Board-specific |
| Pipeline simulation | Python | Algorithm development + testing | Desktop (any OS) |
| Visualization | Python | Real-time spatial visualization | Desktop |
| Test suites | Python | Unit + integration tests | Desktop (pytest) |
| Scenario definitions | JSON | Test environment geometry | — |
| Configuration | JSON + C headers | System parameters | — |

---

## Building and Running

### Option 1: Run the Python Simulation (No Hardware Required)

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/chora.git
cd chora

# Install Python dependencies
pip install -r simulation/requirements.txt

# Run the full pipeline simulation
python simulation/chora_sim.py

# Run with a specific scenario
python simulation/chora_sim.py --scenario simulation/scenarios/plaza.json

# Run with visualization
python simulation/chora_sim.py --visualize

# Run the training scaffold simulation (10-week progression)
python simulation/training_scaffold.py --weeks 10 --plot
```

### Option 2: Build Phase 0 Research Prototype (Raspberry Pi Zero 2W)

```bash
# On the Raspberry Pi:
cd chora/scripts
chmod +x build_prototype.sh
./build_prototype.sh

# This compiles the C firmware for ARM Linux
# and sets up the GPIO, I2C, SPI, and audio interfaces
# for the off-the-shelf hardware prototype:
#   - MEMS ultrasonic breakout boards on GPIO
#   - BMI270 IMU on I2C
#   - USB audio for bone conduction headphones
#   - BLE via hci0 for wristband link
```

### Option 3: Build for Production Target (Alif Ensemble E7)

```bash
# Prerequisites: Zephyr SDK 3.5+, ARM GCC 12.2+
# Set up Zephyr workspace
west init -m https://github.com/YOUR_USERNAME/chora
west update

# Build
west build -b alif_e7 -- -DSHIELD=chora_glasses

# Flash
west flash

# Monitor serial output
west espressif monitor  # or: minicom -D /dev/ttyACM0 -b 115200
```

### Option 4: Run Tests

```bash
# All tests
cd chora
python -m pytest tests/ -v

# Unit tests only
python -m pytest tests/unit/ -v

# Specific test
python -m pytest tests/unit/test_acoustic_grammar.py -v

# With coverage
python -m pytest tests/ --cov=simulation --cov-report=html
```

---

## DIKW Training Scaffold

The training follows the **DIKW pyramid** (Data → Information → Knowledge → Wisdom), treating the human cortex as an AI model being trained:

```
    ╔══════════╗
    ║  WISDOM  ║  Weeks 9–10: 0–10% augmentation
    ║  ~~~~~~  ║  User navigates novel spaces with natural clicks alone
    ║ DEPLOYED ║  The "model" runs permanently in wetware
    ╠══════════╣
    ║KNOWLEDGE ║  Weeks 6–8: 25–50% augmentation
    ║  ~~~~~~  ║  Cortical model generalizing, handles familiar spaces
    ║VALIDATED ║  V1 grey matter density measurably increased
    ╠══════════╣
    ║  INFO    ║  Weeks 3–5: 50–80% augmentation
    ║  ~~~~~~  ║  User recognizes echo patterns, some discrimination
    ║ TRAINING ║  Like supervised learning with teacher forcing
    ╠══════════╣
    ║  DATA    ║  Weeks 1–2: 90–100% augmentation
    ║  ~~~~~~  ║  Raw signal exposure, user learns click technique
    ║COLLECTED ║  Brain receives structured signal it cannot yet generate
    ╚══════════╝
```

| ML Pipeline Stage | Chōra Equivalent | What Happens |
|-------------------|-----------------|--------------|
| Data Collection | Weeks 1–2 | Device captures click→echo pairs with LiDAR ground truth |
| Training | Weeks 3–6 | Full augmentation teaches cortex echo→geometry mapping |
| Validation | Weeks 7–8 | Reduced augmentation tests generalization |
| Testing | Weeks 9–10 | Near-zero augmentation in novel environments |
| Deployment | Post-training | The "model" (cortex) runs permanently, zero power |

**Adaptive scaffolding:** if the user's accuracy drops below 60%, augmentation temporarily increases. If accuracy exceeds 90%, augmentation fades faster. The system never lets the user fail — like curriculum learning in ML.

---

## Fleet Learning — How Users Sharpen the System

Like Tesla's fleet improves Autopilot from driving data, every Chōra navigator's echo data improves the system for future navigators:

- **Anonymized session metrics** (accuracy curves, failure patterns) upload via BLE → phone → cloud
- **Federated learning**: acoustic models train locally, only gradients leave the device
- **No raw audio stored**: privacy-by-design, not policy
- **Cross-city transfer**: a plaza in Guayaquil sharpens models for a plaza in Madrid
- **Common failure patterns** (fountains, glass facades, construction) get pre-trained recognition

**Users are not consumers of the technology. They are co-authors of it.**

---

## Contributing

This is research firmware for spatial justice. Contributions welcome in:

- **Embedded DSP**: pipeline optimization, CMSIS-DSP integration, Ethos-U55 NPU offload
- **HRTF personalization**: algorithms for adapting HRTF to individual head geometry
- **Point cloud compression**: efficient BLE uplink for fleet learning
- **Haptic pattern design**: new vibrotactile textures for novel materials
- **Acoustic grammar extensions**: additional equations for wind, rain, traffic
- **Python simulation**: new test scenarios, visualization improvements
- **Documentation**: translations, hardware build guides, user study protocols

### Code Style

- **C firmware**: K&R style, 4-space indent, descriptive function names prefixed with module (`ag_`, `rir_`, `haptic_`, `scaffold_`)
- **Python simulation**: PEP 8, type hints, docstrings on all public functions
- **Commits**: conventional commits (`feat:`, `fix:`, `docs:`, `test:`)

---

## Research Foundation

Chōra is built on published research in:

- **Computational acoustics**: the four-equation acoustic grammar formalization
- **Blind spatial cognition**: the Sonic Strike fieldwork protocol (27 visits, 5 temporal conditions)
- **Cortical neuroplasticity**: Norman, Hartley & Thaler (2024) — echolocation training produces V1 activation and grey matter growth in A1
- **Phygital urban systems**: the Hyper-Connector IoT prototype
- **Spatial justice**: the BlindSpace theoretical framework — oculocentric design as measurable injustice

The system addresses what the research names as **oculocentrism**: the assumption that all spatial design must be visual. Chōra proves that sound is not a supplement to visual data — it is, at the physics level, an equally rigorous spatial description.

---

## License

MIT License — see [LICENSE](LICENSE)

Free to use, modify, and distribute. If you build something with Chōra, we'd love to hear about it.

---

<p align="center">
<strong>Chōra</strong> — Telecommunications & Electronics Engineering × Spatial Justice<br>
<em>The device teaches, then fades. The spatial map lives in the cortex permanently.</em>
</p>

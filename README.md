CHORA — ECHOLOCATION AUGMENTATION SYSTEM
  
  The autonomous vehicle navigation stack, compressed into sunglasses,
  that trains the human brain to navigate like a bat — then turns itself off.
════════════════════════════════════════════════════════════════════════════════

  Chora (from Greek khora) — Plato's Timaeus: the receptacle of space 
  itself, neither form nor matter, but the medium through which both 
  become possible. Here, Chora is the acoustic medium through which 
  blind navigators perceive, co-author, and inhabit public space.

  License:    MIT (free to use, modify, distribute)
  Languages:  C99 (embedded firmware) + Python 3.10+ (simulation)
  Platform:   ARM Cortex-M55 + Ethos-U55 NPU (Alif Ensemble E7)
  RTOS:       Zephyr 3.5
  Status:     Research Prototype


────────────────────────────────────────────────────────────────────────────────
  TABLE OF CONTENTS
────────────────────────────────────────────────────────────────────────────────

  1.  What Is Chora?
  2.  The Problem It Solves
  3.  How It Works — The 8ms Pipeline
  4.  The Four Core Equations
  5.  Hardware Architecture
  6.  Software Architecture
  7.  Repository Structure (All Files)
  8.  Languages and Technologies
  9.  How to Build and Run
  10. DIKW Training Scaffold
  11. Fleet Learning
  12. Contributing
  13. Research Foundation


────────────────────────────────────────────────────────────────────────────────
  1. WHAT IS CHORA?
────────────────────────────────────────────────────────────────────────────────

Chora is an open-source embedded firmware and simulation platform for a
wearable echolocation augmentation device. The physical device is a pair
of sunglasses and a wristband that:

  1. SCANS the environment using miniaturized LiDAR and ultrasonic MEMS 
     transducers

  2. DETECTS the user's mouth clicks with sub-millisecond precision

  3. PREDICTS what the echo should sound like by ray-casting through the 
     3D point cloud

  4. DELIVERS an augmented echo through bone conduction speakers — richer 
     and more spatially precise than what the environment naturally returns

  5. MAPS the spatial field onto a 3x3 haptic grid on the wristband

  6. PROGRESSIVELY FADES over 10 weeks as the user's visual cortex learns 
     to decode acoustic echoes as spatial geometry

After training, the user navigates with their own unassisted mouth clicks.
The spatial map lives in their cortex permanently. No battery required.


────────────────────────────────────────────────────────────────────────────────
  2. THE PROBLEM IT SOLVES
────────────────────────────────────────────────────────────────────────────────

Every existing assistive navigation technology does the same thing: it takes
information from the environment and converts it into an INSTRUCTION. A beep 
says "stop." A GPS voice says "turn left." A vibrating watch says "obstacle 
ahead."

The human is always the RECEIVER, never the GENERATOR. The device always 
knows more than the person. Permanently.

CHORA INVERTS THIS. The device starts knowing more — the LiDAR has 
millimetre-precision geometry — but it uses that knowledge to TEACH, not 
to instruct. Over weeks, the brain learns to read echoes as spatial geometry.
The device fades. The user graduates to navigating with their own clicks.

This is not an accessibility add-on. It is a SPATIAL AUTONOMY SYSTEM that 
treats blind navigators as the primary engineers of their own perception.


────────────────────────────────────────────────────────────────────────────────
  3. HOW IT WORKS — THE 8ms PIPELINE
────────────────────────────────────────────────────────────────────────────────

When the user makes a mouth click, the entire pipeline executes in 
8 milliseconds — below the 10ms human auditory fusion threshold. 
The brain cannot distinguish the augmented echo from the natural echo.

  CLICK DETECT ──> LiDAR CAPTURE ──> RAY CAST ──> MATERIAL ID
      0.5ms            2.0ms           1.0ms         1.0ms

  ──> RIR SYNTHESIS ──> HRTF RENDER ──> BONE OUTPUT + HAPTIC MAP
         1.5ms            1.0ms           0.5ms        0.5ms

  TOTAL: 8.0ms

Pipeline Stages:

  Stage 1: CLICK DETECT (0.5ms)
    File: src/drivers/mems_driver.c
    MEMS microphone detects mouth click onset, classifies type 
    (tongue/mouth/finger), measures energy and peak frequency.

  Stage 2: LiDAR CAPTURE (2.0ms)
    File: src/drivers/lidar_driver.c
    Two solid-state dToF sensors capture 3D point cloud (up to 2048 
    points), voxelized into spatial occupancy grid.

  Stage 3: RAY CAST (1.0ms)
    File: src/dsp/acoustic_grammar.c
    Acoustic rays cast through voxel grid in click propagation cone 
    (+/-60 deg x +/-30 deg), finds surface intersections.

  Stage 4: MATERIAL ID (1.0ms)
    File: src/dsp/acoustic_grammar.c
    FFT sub-band analysis classifies surface materials: concrete, glass,
    metal, wood, foliage, water, human body.

  Stage 5: RIR SYNTHESIS (1.5ms)
    File: src/dsp/rir_engine.c
    Predicts Room Impulse Response — what the echo SHOULD sound like
    given the 3D geometry.

  Stage 6: HRTF RENDER (1.0ms)
    File: src/dsp/rir_engine.c
    Spatializes each echo return to its 3D direction using Head-Related 
    Transfer Functions, produces binaural output.

  Stage 7: BONE OUTPUT (0.5ms)
    File: src/main.c
    Writes binaural audio to I2S DMA for bone conduction piezo drivers 
    at cheekbones.

  Stage 8: HAPTIC MAP (0.5ms)
    File: src/haptic/haptic_mapper.c
    Converts echo field into 3x3 vibrotactile pattern, transmits via 
    BLE to wristband.


────────────────────────────────────────────────────────────────────────────────
  4. THE FOUR CORE EQUATIONS
────────────────────────────────────────────────────────────────────────────────

These are not metaphors. They ARE engineering — the same mathematics 
used in radar, 5G propagation, and MIMO beamforming.

EQUATION 1 — Echo Distance (Time-of-Arrival Ranging)

    d = c * dt / 2

    Identical to radar/sonar/UWB indoor positioning. The click's 
    round-trip delay gives distance. Temperature-corrected:
    c = 331.3 + 0.606 * T (degrees C).
    
    Telecoms equivalent: ToA ranging, FMCW radar, UWB localization.
    Implemented in: src/dsp/acoustic_grammar.c, function ag_compute_distance()
    Python mirror: simulation/acoustic_grammar.py, function echo_distance()


EQUATION 2 — Atmospheric Attenuation

    alpha(f) = 1.17 x 10^-5 * f^2

    Frequency-dependent energy loss over distance. Higher frequencies
    attenuate faster — this is why material textures (high-band) fade
    before room geometry (low-band).
    
    Telecoms equivalent: Friis transmission equation, 5G mmWave path loss.
    Implemented in: src/dsp/acoustic_grammar.c, function ag_atmospheric_attenuation()
    Python mirror: simulation/acoustic_grammar.py, function atmospheric_attenuation()


EQUATION 3 — Harmonic Interference Field

    Hi = |SUM( Aj * e^(i*phij) )|

    Multi-source phase superposition. When multiple surfaces reflect the 
    click, their echoes interfere constructively or destructively. This 
    pattern encodes 3D room geometry.
    
    Telecoms equivalent: MIMO beamforming, phased array steering, DoA.
    Implemented in: src/dsp/acoustic_grammar.c, function ag_harmonic_interference()
    Python mirror: simulation/acoustic_grammar.py, function harmonic_interference()


EQUATION 4 — Environmental Channel Model

    alpha(f,H) = k * f^2 * e^(-beta*H)

    Humidity-dependent propagation model. Compensates for environmental 
    conditions that affect echo quality.
    
    Telecoms equivalent: ITU-R P.676, mmWave rain fade.
    Implemented in: src/dsp/acoustic_grammar.c, function ag_environmental_channel()
    Python mirror: simulation/acoustic_grammar.py, function environmental_channel()


────────────────────────────────────────────────────────────────────────────────
  5. HARDWARE ARCHITECTURE
────────────────────────────────────────────────────────────────────────────────

-- GLASSES UNIT (38g total) --

  Component         Part                      Location         Power
  ──────────────    ────────────────────────   ──────────────   ──────
  MCU + NPU         Alif Ensemble E7          Right temple     280mW
                    ARM Cortex-M55 @ 800MHz
                    + Ethos-U55 (160 GOPS)

  LiDAR x 2        Solid-state dToF          Inner top frame  120mW
                    15m range, 4.2x5mm
                    20fps point cloud

  MEMS TX x 2      Murata MA40S4S            Temple tips       15mW
                    40kHz piezo transducer

  MEMS RX x 2      Knowles SPH0645           Lower frame        3mW
                    PDM microphone, -26dB SNR

  Bone Cond. x 2   Knowles BU-27135          Cheekbone pads    90mW
                    Piezo driver, 200Hz-8kHz

  IMU               Bosch BMI270              Bridge center      4mW
                    6-axis (accel + gyro)

  BLE Radio         Nordic nRF5340            Left temple       22mW
                    BLE 5.3, 2Mbps PHY

  Battery           Li-Po 800mAh              Both temples       --
                    USB-C charging

  TOTAL ACTIVE POWER: ~534mW = ~6 hours runtime


-- WRISTBAND UNIT (28g total) --

  Component         Part                      Power
  ──────────────    ────────────────────────   ──────
  Haptic Array      9x TDK PowerHap 1204H     450mW peak
                    3x3 grid, 250Hz resonant

  BLE Co-Proc       nRF52832                   18mW

  Battery           Li-Po 400mAh               --
                    ~8hr runtime

-- HAPTIC GRID LAYOUT (user's wrist, palm up) --

    +----------+----------+----------+
    |  Far-L   |  Far-C   |  Far-R   |  Row 0: 5-15m range
    +----------+----------+----------+
    |  Mid-L   |  Mid-C   |  Mid-R   |  Row 1: 1.5-5m range
    +----------+----------+----------+
    |  Near-L  |  Near-C  |  Near-R  |  Row 2: 0-1.5m range
    +----------+----------+----------+
    
    Columns: Left / Center / Right azimuth sectors
    Intensity: detection confidence (0-100%)
    Frequency: material encoding (stone=70Hz, glass=280Hz, metal=250Hz)
    Pattern: continuous / pulse / ramp / burst


────────────────────────────────────────────────────────────────────────────────
  6. SOFTWARE ARCHITECTURE
────────────────────────────────────────────────────────────────────────────────

    +----------------------------------------------------------+
    |               APPLICATION LAYER                           |
    |  training/scaffold.c  |  navigation  |  codesign_uplink   |
    +----------------------------------------------------------+
    |               DSP / ML LAYER                              |
    |  dsp/acoustic_grammar.c | dsp/rir_engine.c | point_cloud  |
    +----------------------------------------------------------+
    |            HARDWARE ABSTRACTION LAYER                      |
    |  drivers/lidar_driver.c | drivers/mems_driver.c | audio   |
    +----------------------------------------------------------+
    |                HAL / RTOS / FIRMWARE                       |
    |  main.c | include/core/hal.h | BLE stack | power mgmt     |
    +----------------------------------------------------------+


────────────────────────────────────────────────────────────────────────────────
  7. REPOSITORY STRUCTURE (ALL FILES)
────────────────────────────────────────────────────────────────────────────────

chora/
|
|-- README.md ..................... Full documentation (Markdown version)
|-- README.txt ................... This file (plain text version)
|-- LICENSE ....................... MIT License
|-- .gitignore ................... Git ignore rules
|
|-- include/ ..................... C HEADER FILES
|   |-- core/
|   |   |-- pipeline.h ........... Master data structures, all types
|   |   |                          (point cloud, echo field, haptic grid,
|   |   |                           audio frame, training state, IMU data)
|   |   +-- hal.h ................ Hardware Abstraction Layer interface
|   |                              (GPIO, SPI, I2C, ADC, DAC, PWM, PDM,
|   |                               I2S, BLE — platform-independent)
|   |-- drivers/ ................. (interface headers for drivers)
|   |-- dsp/ ..................... (interface headers for DSP)
|   |-- haptic/ .................. (interface headers for haptic)
|   +-- training/ ................ (interface headers for training)
|
|-- src/ ......................... C SOURCE FILES (Embedded Firmware)
|   |
|   |-- main.c ................... PIPELINE ORCHESTRATOR (356 lines)
|   |                              - Initializes all hardware subsystems
|   |                              - Runs the 8ms real-time loop
|   |                              - Click detection interrupt handler
|   |                              - Audio output double-buffering (I2S DMA)
|   |                              - IMU orientation fusion (complementary filter)
|   |                              - Main application entry point
|   |
|   |-- drivers/
|   |   |-- lidar_driver.c ....... LiDAR POINT CLOUD CAPTURE (350 lines)
|   |   |                          - SPI communication with 2x dToF sensors
|   |   |                          - Pixel-to-3D-point conversion
|   |   |                          - Point cloud voxelization
|   |   |                          - Surface normal estimation (PCA)
|   |   |                          - Power mode management
|   |   |
|   |   +-- mems_driver.c ........ MEMS ULTRASONIC + CLICK DETECT (420 lines)
|   |                              - 40kHz FM chirp waveform generation
|   |                              - Echo capture via ADC DMA
|   |                              - Cross-correlation for ToA distance
|   |                              - TDoA angle estimation (binaural)
|   |                              - Click onset detection (energy threshold)
|   |                              - Click type classification
|   |                              - Environmental speed-of-sound correction
|   |
|   |-- dsp/
|   |   |-- acoustic_grammar.c ... FOUR EQUATIONS DSP ENGINE (480 lines)
|   |   |                          - Equation 1: echo_distance (ToA)
|   |   |                          - Equation 2: atmospheric_attenuation
|   |   |                          - Equation 3: harmonic_interference (phased array)
|   |   |                          - Equation 4: environmental_channel (humidity)
|   |   |                          - 256-point radix-2 FFT implementation
|   |   |                          - Material classification from spectrum
|   |   |                          - Ray casting through voxel grid
|   |   |                          - Three-band spectrum computation
|   |   |
|   |   +-- rir_engine.c ......... RIR SYNTHESIS + HRTF RENDERER (370 lines)
|   |                              - HRTF database (72 directions, 5 deg resolution)
|   |                              - Woodworth spherical head model (ITD + ILD)
|   |                              - Room Impulse Response synthesis from echo field
|   |                              - Binaural spatialization (per-echo HRTF convolution)
|   |                              - Three-band grammar signal synthesis
|   |                              - Soft-clip output protection
|   |
|   |-- haptic/
|   |   +-- haptic_mapper.c ...... HAPTIC GRID MAPPER (280 lines)
|   |                              - Echo field to 3x3 grid spatial binning
|   |                              - Material-to-vibration texture mapping
|   |                              - BLE packet encoding (27 bytes)
|   |                              - Wristband actuator PWM control
|   |
|   +-- training/
|       +-- scaffold.c ........... DIKW TRAINING SCAFFOLD (360 lines)
|                                  - 5-phase training schedule (weeks 1-10)
|                                  - Adaptive augmentation computation
|                                  - Click accuracy measurement
|                                  - DIKW level assessment
|                                  - Session management
|                                  - Fleet learning data logging
|
|-- simulation/ .................. PYTHON SIMULATION
|   |-- requirements.txt ......... Python dependencies (numpy, scipy, etc.)
|   |-- acoustic_grammar.py ...... Four equations in Python (480 lines)
|   |                              - All data structures (EchoReturn, EchoField, etc.)
|   |                              - Material properties database
|   |                              - Ray-rectangle intersection
|   |                              - Full ray casting with echo field output
|   |                              - Material classification
|   |-- chora_sim.py ............. Full pipeline simulation (580 lines)
|   |                              - Haptic grid mapping
|   |                              - RIR synthesis
|   |                              - Binaural HRTF rendering
|   |                              - Training scaffold simulation
|   |                              - CLI interface with arguments
|   |                              - Default plaza scenario
|   +-- scenarios/
|       +-- plaza.json ........... Plaza de Olavide scenario definition
|                                  (12 obstacles, materials, dimensions)
|
|-- tests/ ....................... TEST SUITES
|   +-- unit/
|       +-- test_acoustic_grammar.py  Unit tests (19 tests, ALL PASSING)
|                                     - Equation 1: distance computation
|                                     - Equation 2: attenuation physics
|                                     - Equation 3: interference (constructive/destructive)
|                                     - Equation 4: humidity dependency
|                                     - Ray casting integration
|                                     - Three-band spectrum verification
|
|-- scripts/ ..................... BUILD AND RUN SCRIPTS
|   |-- run_simulation.sh ........ Launch Python simulation
|   +-- run_tests.sh ............. Run all test suites
|
|-- config/ ...................... Configuration files (expandable)
|-- boards/alif_e7/ .............. Board-specific definitions (expandable)
|-- firmware/wristband/ .......... Wristband nRF52832 firmware (expandable)
|-- docs/ ........................ Documentation (expandable)
    |-- architecture/ ............ System architecture docs
    |-- equations/ ............... Mathematical derivations
    +-- hardware/ ................ BOM, PCB notes, power budget


────────────────────────────────────────────────────────────────────────────────
  8. LANGUAGES AND TECHNOLOGIES
────────────────────────────────────────────────────────────────────────────────

This project uses TWO LANGUAGES for two different purposes:

C99 — EMBEDDED FIRMWARE (src/ and include/)
  3,114 lines of code
  Runs on the ARM Cortex-M55 processor inside the sunglasses.
  
  Why C?
    - Deterministic timing: 8ms pipeline budget, no garbage collection
    - Direct hardware access: SPI, I2C, PDM, I2S, PWM, BLE registers
    - Memory efficiency: all buffers statically allocated, no heap
    - RTOS compatibility: Zephyr real-time thread priorities
    - DSP optimization: ARM CMSIS-DSP intrinsics for FFT and filtering
  
  Toolchain: ARM GCC 12.2+, Zephyr SDK 3.5+, CMake 3.20+


PYTHON 3.10+ — SIMULATION AND TESTING (simulation/ and tests/)
  1,062 lines of code
  Runs on any desktop/laptop for algorithm development and testing.
  
  Why Python?
    - Rapid prototyping: test changes without flashing hardware
    - Visualization: matplotlib, pygame for real-time display
    - Scientific computing: NumPy/SciPy for FFT, signal processing
    - Test framework: pytest for unit, integration, simulation tests
  
  Dependencies: numpy, scipy, matplotlib, pygame, pytest


SUMMARY TABLE:

  Component               Language    Purpose
  ──────────────────────  ──────────  ──────────────────────────────
  Pipeline firmware       C99         Real-time 8ms signal chain
  Wristband firmware      C99         Haptic actuator control
  HAL interface           C99         Hardware abstraction
  Pipeline simulation     Python      Algorithm development + testing
  Test suites             Python      Unit + integration tests (pytest)
  Scenario definitions    JSON        Test environment geometry
  Configuration           JSON + C    System parameters


────────────────────────────────────────────────────────────────────────────────
  9. HOW TO BUILD AND RUN
────────────────────────────────────────────────────────────────────────────────

OPTION 1: RUN THE PYTHON SIMULATION (No Hardware Required)

    # Clone or download the repository
    cd chora
    
    # Install Python dependencies
    pip install -r simulation/requirements.txt
    
    # Run the full pipeline simulation
    python simulation/chora_sim.py
    
    # Run with a specific training week (1-10)
    python simulation/chora_sim.py --week 5
    
    # Run with more click cycles
    python simulation/chora_sim.py --week 3 --clicks 20
    
    # Run the test suite (19 tests)
    python -m pytest tests/ -v


OPTION 2: BUILD FOR RASPBERRY PI ZERO 2W (Phase 0 Research Prototype)

    # On the Raspberry Pi:
    cd chora/scripts
    chmod +x build_prototype.sh
    ./build_prototype.sh


OPTION 3: BUILD FOR PRODUCTION TARGET (Alif Ensemble E7)

    # Prerequisites: Zephyr SDK 3.5+, ARM GCC 12.2+
    west init -m https://github.com/YOUR_USERNAME/chora
    west update
    west build -b alif_e7
    west flash


OPTION 4: RUN TESTS ONLY

    cd chora
    python -m pytest tests/unit/ -v
    
    Expected output: 19 passed


────────────────────────────────────────────────────────────────────────────────
  10. DIKW TRAINING SCAFFOLD
────────────────────────────────────────────────────────────────────────────────

The training follows the DIKW pyramid (Data, Information, Knowledge, Wisdom),
treating the human cortex as an AI model being trained:

    +============+
    |   WISDOM   |  Weeks 9-10: 0-10% augmentation
    |  DEPLOYED  |  User navigates novel spaces with natural clicks
    +============+  The "model" runs permanently in wetware
    | KNOWLEDGE  |  Weeks 6-8: 25-50% augmentation
    | VALIDATED  |  Cortical model generalizing, handles familiar spaces
    +============+  V1 grey matter density measurably increased
    |    INFO    |  Weeks 3-5: 50-80% augmentation
    |  TRAINING  |  User recognizes echo patterns, some discrimination
    +============+  Like supervised learning with teacher forcing
    |    DATA    |  Weeks 1-2: 90-100% augmentation
    | COLLECTED  |  Raw signal exposure, user learns click technique
    +============+  Brain receives structured signal it cannot yet generate

  ML Pipeline       Chora Equivalent       What Happens
  ──────────────    ──────────────────     ───────────────────────────────
  Data Collection   Weeks 1-2              Device captures click-echo pairs
  Training          Weeks 3-6              Full augmentation teaches cortex
  Validation        Weeks 7-8              Reduced augmentation tests skill
  Testing           Weeks 9-10             Near-zero in novel environments
  Deployment        Post-training          Cortex runs permanently, 0 power

Adaptive scaffolding: if accuracy drops below 60%, augmentation temporarily
increases. If accuracy exceeds 90%, augmentation fades faster. The system
never lets the user fail.


────────────────────────────────────────────────────────────────────────────────
  11. FLEET LEARNING — HOW USERS SHARPEN THE SYSTEM
────────────────────────────────────────────────────────────────────────────────

Like Tesla's fleet improves Autopilot from driving data, every Chora
navigator's echo data improves the system for future navigators:

  - Anonymized session metrics upload via BLE > phone > cloud
  - Federated learning: acoustic models train locally, only gradients leave
  - No raw audio stored: privacy-by-design, not policy
  - Cross-city transfer: a plaza in Guayaquil sharpens models for Madrid
  - Common failure patterns get pre-trained recognition

Users are not consumers of the technology. They are co-authors of it.


────────────────────────────────────────────────────────────────────────────────
  12. CONTRIBUTING
────────────────────────────────────────────────────────────────────────────────

This is research firmware for spatial justice. Contributions welcome in:

  - Embedded DSP optimization (CMSIS-DSP, Ethos-U55 NPU offload)
  - HRTF personalization algorithms
  - Point cloud compression for BLE uplink
  - Haptic pattern design for new materials
  - Acoustic grammar extensions (wind, rain, traffic)
  - Python simulation improvements and new scenarios
  - Documentation and translations

Code style:
  C firmware: K&R style, 4-space indent, module-prefixed functions
  Python: PEP 8, type hints, docstrings
  Commits: conventional commits (feat:, fix:, docs:, test:)


────────────────────────────────────────────────────────────────────────────────
  13. RESEARCH FOUNDATION
────────────────────────────────────────────────────────────────────────────────

Chora is built on published research in:

  - Computational acoustics: four-equation acoustic grammar formalization
  - Blind spatial cognition: Sonic Strike fieldwork protocol
    (27 visits, 5 temporal conditions)
  - Cortical neuroplasticity: Norman, Hartley & Thaler (2024) —
    echolocation training produces V1 activation and grey matter growth
  - Phygital urban systems: Hyper-Connector IoT prototype
  - Spatial justice: BlindSpace theoretical framework —
    oculocentric design as measurable injustice

The system addresses oculocentrism: the assumption that all spatial design
must be visual. Chora proves that sound is, at the physics level, an equally
rigorous spatial description.


────────────────────────────────────────────────────────────────────────────────
  LICENSE
────────────────────────────────────────────────────────────────────────────────

MIT License — see LICENSE file.
Free to use, modify, and distribute.


════════════════════════════════════════════════════════════════════════════════
  Chora — Telecommunications & Electronics Engineering x Spatial Justice
  The device teaches, then fades. The spatial map lives in the cortex.
════════════════════════════════════════════════════════════════════════════════

"""
Chōra — Full Pipeline Simulation

Simulates the complete echolocation augmentation pipeline:
    Click → LiDAR → Ray Cast → Material ID → RIR → HRTF → Output + Haptic

Run:
    python chora_sim.py                          # Default plaza scenario
    python chora_sim.py --scenario plaza.json     # Specific scenario
    python chora_sim.py --visualize               # With real-time display
    python chora_sim.py --week 5                  # Set training week (1-10)
"""

import numpy as np
import json
import argparse
import time
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple

from acoustic_grammar import (
    EchoField, EchoReturn, Obstacle, Material,
    MATERIALS, SPEED_OF_SOUND, SAMPLE_RATE,
    ray_cast_2d, compute_three_band_spectrum,
    echo_distance, atmospheric_attenuation,
    harmonic_interference, environmental_channel
)


# ═══════════════════════════════════════════════════════════
# HAPTIC GRID MAPPING
# ═══════════════════════════════════════════════════════════

HAPTIC_ROWS = 3
HAPTIC_COLS = 3
RANGE_NEAR = 1.5    # meters
RANGE_MID = 5.0
RANGE_FAR = 15.0
AZ_LEFT = -0.5236   # -30°
AZ_RIGHT = 0.5236   # +30°


@dataclass
class HapticCell:
    intensity: float = 0.0
    frequency: float = 150.0
    pattern: int = 0
    material: Material = Material.UNKNOWN


MATERIAL_HAPTIC = {
    Material.UNKNOWN:  (150.0, 0),
    Material.CONCRETE: (80.0,  0),
    Material.STONE:    (70.0,  0),
    Material.WOOD:     (180.0, 0),
    Material.GLASS:    (280.0, 2),
    Material.METAL:    (250.0, 3),
    Material.FOLIAGE:  (120.0, 1),
    Material.WATER:    (200.0, 1),
    Material.FABRIC:   (100.0, 0),
    Material.HUMAN:    (160.0, 1),
}


def map_echo_to_haptic(
    echo_field: EchoField,
    augmentation: float = 1.0
) -> List[List[HapticCell]]:
    """
    Convert echo field into 3×3 haptic grid.
    
    Grid layout:
        [Far-L]  [Far-C]  [Far-R]     Row 0
        [Mid-L]  [Mid-C]  [Mid-R]     Row 1
        [Near-L] [Near-C] [Near-R]    Row 2
    """
    grid = [[HapticCell() for _ in range(HAPTIC_COLS)] 
            for _ in range(HAPTIC_ROWS)]
    
    for echo in echo_field.returns:
        # Column from azimuth
        if echo.azimuth < AZ_LEFT:
            col = 0
        elif echo.azimuth > AZ_RIGHT:
            col = 2
        else:
            col = 1
        
        # Row from distance
        if echo.distance < RANGE_NEAR:
            row = 2
        elif echo.distance < RANGE_MID:
            row = 1
        else:
            row = 0
        
        # Intensity (inverse distance, weighted by amplitude)
        proximity = min(1.0, RANGE_NEAR / max(echo.distance, 0.1))
        intensity = echo.amplitude * proximity * augmentation
        
        cell = grid[row][col]
        if intensity > cell.intensity:
            cell.intensity = min(1.0, intensity)
            cell.material = echo.material
            freq, pattern = MATERIAL_HAPTIC.get(
                echo.material, (150.0, 0)
            )
            cell.frequency = freq * (0.7 + 0.3 * cell.intensity)
            cell.pattern = pattern
    
    return grid


# ═══════════════════════════════════════════════════════════
# RIR SYNTHESIS (Simplified for simulation)
# ═══════════════════════════════════════════════════════════

def synthesize_rir(
    echo_field: EchoField,
    duration_samples: int = 512
) -> np.ndarray:
    """
    Synthesize Room Impulse Response from echo field.
    Each echo contributes a delayed, filtered impulse.
    """
    rir = np.zeros(duration_samples)
    
    for echo in echo_field.returns:
        delay_samples = int(echo.delay * SAMPLE_RATE)
        if delay_samples >= duration_samples - 32:
            continue
        
        mat = MATERIALS[echo.material]
        f_center = (mat.freq_low + mat.freq_high) / 2.0
        decay_rate = 1000.0 * (1.0 + mat.absorption * 5.0)
        
        for t in range(min(32, duration_samples - delay_samples)):
            time_s = t / SAMPLE_RATE
            envelope = echo.amplitude * np.exp(-time_s * decay_rate)
            signal = envelope * np.sin(2 * np.pi * f_center * time_s)
            rir[delay_samples + t] += signal
    
    return rir


# ═══════════════════════════════════════════════════════════
# BINAURAL HRTF RENDERING (Simplified)
# ═══════════════════════════════════════════════════════════

def render_binaural(
    echo_field: EchoField,
    augmentation: float = 1.0,
    block_size: int = 256
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Render binaural audio from echo field.
    Uses simplified panning model (production uses measured HRTFs).
    
    Returns:
        (left_channel, right_channel) audio arrays
    """
    left = np.zeros(block_size)
    right = np.zeros(block_size)
    
    for echo in echo_field.returns:
        onset = int(echo.delay * SAMPLE_RATE)
        if onset >= block_size:
            continue
        
        mat = MATERIALS[echo.material]
        f_center = (mat.freq_low + mat.freq_high) / 2.0
        amp = echo.amplitude * augmentation
        
        # Simple panning from azimuth
        pan = np.sin(echo.azimuth)
        gain_left = 0.5 - 0.5 * pan
        gain_right = 0.5 + 0.5 * pan
        
        for t in range(min(32, block_size - onset)):
            time_s = t / SAMPLE_RATE
            decay = np.exp(-time_s * 800.0 * (1 + mat.absorption))
            sample = amp * decay * np.sin(2 * np.pi * f_center * time_s)
            left[onset + t] += sample * gain_left
            right[onset + t] += sample * gain_right
    
    # Soft clip
    left = np.tanh(left * 2.0) * 0.5
    right = np.tanh(right * 2.0) * 0.5
    
    return left, right


# ═══════════════════════════════════════════════════════════
# TRAINING SCAFFOLD
# ═══════════════════════════════════════════════════════════

DIKW_LABELS = {0: "DATA", 1: "INFORMATION", 2: "KNOWLEDGE", 3: "WISDOM"}

def compute_augmentation(week: int, accuracy: float = 0.5) -> float:
    """Compute augmentation level from training week and accuracy."""
    schedule = [
        (1, 2, 1.00, 0.90),
        (3, 4, 0.80, 0.60),
        (5, 6, 0.50, 0.35),
        (7, 8, 0.25, 0.15),
        (9, 10, 0.10, 0.00),
    ]
    
    for w_start, w_end, aug_start, aug_end in schedule:
        if w_start <= week <= w_end:
            progress = (week - w_start) / (w_end - w_start + 1)
            base = aug_start + (aug_end - aug_start) * progress
            
            # Adaptive: boost if struggling, speed up if excelling
            if accuracy < 0.6 and base < 0.5:
                base = min(base + (0.6 - accuracy) * 0.5, aug_start)
            elif accuracy > 0.9 and base > 0.1:
                base = max(base - (accuracy - 0.9) * 0.3, aug_end)
            
            return np.clip(base, 0.0, 1.0)
    
    return 0.0


def get_dikw_level(week: int, accuracy: float) -> int:
    if week <= 2 or accuracy < 0.4:
        return 0  # DATA
    if week <= 5 or accuracy < 0.7:
        return 1  # INFORMATION
    if accuracy < 0.85:
        return 2  # KNOWLEDGE
    return 3  # WISDOM


# ═══════════════════════════════════════════════════════════
# DEFAULT SCENARIO — Plaza de Olavide
# ═══════════════════════════════════════════════════════════

def default_plaza_scenario() -> List[Obstacle]:
    """Create a simulated plaza with realistic obstacles."""
    return [
        Obstacle(3.0,  1.5, 1.2, 0.3, Material.WOOD,     "Bench A"),
        Obstacle(8.0,  1.0, 0.3, 1.6, Material.STONE,    "Column"),
        Obstacle(10.0, 5.0, 1.4, 0.3, Material.CONCRETE, "Wall"),
        Obstacle(2.0,  6.0, 1.0, 1.0, Material.WATER,    "Fountain"),
        Obstacle(6.0,  4.0, 0.4, 0.4, Material.METAL,    "Bollard"),
        Obstacle(11.0, 2.0, 0.8, 0.8, Material.FOLIAGE,  "Tree"),
        Obstacle(5.0,  6.5, 1.6, 0.2, Material.GLASS,    "Glass Wall"),
        Obstacle(9.0,  7.0, 0.3, 0.3, Material.HUMAN,    "Pedestrian"),
        Obstacle(1.0,  3.5, 1.2, 0.3, Material.WOOD,     "Bench B"),
        Obstacle(7.0,  3.0, 0.3, 0.3, Material.METAL,    "Sign Post"),
    ]


# ═══════════════════════════════════════════════════════════
# MAIN SIMULATION
# ═══════════════════════════════════════════════════════════

def run_simulation(
    obstacles: List[Obstacle],
    user_pos: np.ndarray = None,
    user_heading: float = 0.0,
    week: int = 1,
    num_clicks: int = 10,
    verbose: bool = True
):
    """
    Run complete pipeline simulation.
    
    Args:
        obstacles: Environment geometry
        user_pos: Starting position [x, y]
        user_heading: Starting heading (radians)
        week: Training week (1-10)
        num_clicks: Number of click cycles to simulate
        verbose: Print detailed output
    """
    if user_pos is None:
        user_pos = np.array([5.0, 4.0])
    
    accuracy = 0.3 + 0.05 * week  # Simulated accuracy progression
    augmentation = compute_augmentation(week, accuracy)
    dikw = get_dikw_level(week, accuracy)
    
    if verbose:
        print("=" * 65)
        print(f"  Chōra — Pipeline Simulation")
        print(f"  Training Week: {week}/10")
        print(f"  Augmentation: {augmentation * 100:.0f}%")
        print(f"  DIKW Level: {DIKW_LABELS[dikw]}")
        print(f"  User Position: ({user_pos[0]:.1f}, {user_pos[1]:.1f})")
        print(f"  Heading: {np.degrees(user_heading):.0f}°")
        print(f"  Obstacles: {len(obstacles)}")
        print("=" * 65)
    
    for click_num in range(num_clicks):
        t_start = time.perf_counter()
        
        # ── Stage 1–4: Ray cast + material classification ──
        echo_field = ray_cast_2d(
            origin=user_pos,
            heading=user_heading,
            obstacles=obstacles,
            temperature=22.0,
            humidity=55.0
        )
        
        # ── Stage 5: RIR synthesis ──
        rir = synthesize_rir(echo_field)
        
        # ── Stage 6–7: Binaural rendering ──
        left, right = render_binaural(echo_field, augmentation)
        
        # ── Stage 8: Haptic mapping ──
        haptic_grid = map_echo_to_haptic(echo_field, augmentation)
        
        t_elapsed = (time.perf_counter() - t_start) * 1000  # ms
        
        if verbose:
            print(f"\n── Click #{click_num + 1} ──")
            print(f"  Pipeline: {t_elapsed:.2f}ms")
            print(f"  Echoes: {len(echo_field.returns)}")
            print(f"  Bands: Low={echo_field.band_low:.3f} "
                  f"Mid={echo_field.band_mid:.3f} "
                  f"High={echo_field.band_high:.3f}")
            
            # Detected objects
            seen = {}
            for echo in echo_field.returns:
                mat_name = MATERIALS[echo.material].name
                if mat_name not in seen or echo.distance < seen[mat_name]:
                    seen[mat_name] = echo.distance
            
            print(f"  Detected:")
            for name, dist in sorted(seen.items(), key=lambda x: x[1]):
                print(f"    {name:12s} @ {dist:.1f}m")
            
            # Haptic grid
            print(f"  Haptic grid (intensity):")
            labels = [["Far-L", "Far-C", "Far-R"],
                      ["Mid-L", "Mid-C", "Mid-R"],
                      ["Near-L", "Near-C", "Near-R"]]
            for r in range(3):
                row_str = "    "
                for c in range(3):
                    cell = haptic_grid[r][c]
                    bar = "█" * int(cell.intensity * 8)
                    row_str += f"[{labels[r][c]:6s} {bar:8s}] "
                print(row_str)
        
        # Simulate slight movement
        user_heading += np.random.uniform(-0.1, 0.1)
        user_pos += np.array([
            np.cos(user_heading) * 0.2,
            np.sin(user_heading) * 0.2
        ])
    
    if verbose:
        print(f"\n{'=' * 65}")
        print(f"  Simulation complete. {num_clicks} clicks processed.")
        print(f"  Augmentation: {augmentation * 100:.0f}% "
              f"(Week {week}, {DIKW_LABELS[dikw]})")
        print(f"{'=' * 65}")
    
    return echo_field, haptic_grid


# ═══════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Chōra — Echolocation Augmentation Pipeline Simulation"
    )
    parser.add_argument("--scenario", type=str, default=None,
                        help="Path to scenario JSON file")
    parser.add_argument("--week", type=int, default=1,
                        help="Training week (1-10)")
    parser.add_argument("--clicks", type=int, default=5,
                        help="Number of click cycles")
    parser.add_argument("--visualize", action="store_true",
                        help="Launch real-time visualization")
    parser.add_argument("--x", type=float, default=5.0,
                        help="Starting X position")
    parser.add_argument("--y", type=float, default=4.0,
                        help="Starting Y position")
    parser.add_argument("--heading", type=float, default=0.0,
                        help="Starting heading (degrees)")
    
    args = parser.parse_args()
    
    # Load scenario
    if args.scenario:
        with open(args.scenario) as f:
            data = json.load(f)
        obstacles = [
            Obstacle(
                o["x"], o["y"], o["width"], o["height"],
                Material(o["material"]), o.get("label", "")
            )
            for o in data["obstacles"]
        ]
    else:
        obstacles = default_plaza_scenario()
    
    if args.visualize:
        print("Visualization mode — requires pygame. Run: pip install pygame")
        try:
            from visualizer import run_visualizer
            run_visualizer(obstacles, args.week)
        except ImportError:
            print("pygame not installed. Running text simulation instead.")
            run_simulation(
                obstacles,
                user_pos=np.array([args.x, args.y]),
                user_heading=np.radians(args.heading),
                week=args.week,
                num_clicks=args.clicks
            )
    else:
        run_simulation(
            obstacles,
            user_pos=np.array([args.x, args.y]),
            user_heading=np.radians(args.heading),
            week=args.week,
            num_clicks=args.clicks
        )


if __name__ == "__main__":
    main()

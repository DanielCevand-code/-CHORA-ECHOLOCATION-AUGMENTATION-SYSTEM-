"""
Chōra — Acoustic Grammar (Python Simulation)

Implements the four core equations that form the computational
grammar of spatial echolocation. This Python version mirrors the
C firmware in src/dsp/acoustic_grammar.c for algorithm verification,
visualization, and rapid prototyping.

Equations:
    1. d = c · Δτ / 2              (Echo Distance — ToA ranging)
    2. α(f) = 1.17e-5 · f²         (Atmospheric Attenuation)
    3. Hᵢ = |Σ Aⱼ·e^(iφⱼ)|        (Harmonic Interference Field)
    4. α(f,H) = k·f²·e^(-βH)       (Environmental Channel Model)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional
from enum import IntEnum


# ═══════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════

SPEED_OF_SOUND = 343.0          # m/s at 20°C
ULTRASONIC_FREQ = 40_000        # Hz
LIDAR_RANGE = 15.0              # meters
SAMPLE_RATE = 48_000            # Hz
PIPELINE_BUDGET_MS = 8.0        # ms


# ═══════════════════════════════════════════════════════════
# MATERIAL DEFINITIONS
# ═══════════════════════════════════════════════════════════

class Material(IntEnum):
    UNKNOWN  = 0
    CONCRETE = 1
    STONE    = 2
    WOOD     = 3
    GLASS    = 4
    METAL    = 5
    FOLIAGE  = 6
    WATER    = 7
    FABRIC   = 8
    HUMAN    = 9


@dataclass
class MaterialProperties:
    name: str
    absorption: float       # 0.0 = perfect reflector, 1.0 = full absorber
    freq_low: float         # Lower frequency response (Hz)
    freq_high: float        # Upper frequency response (Hz)
    scatter: float          # Diffusion coefficient
    color: str              # For visualization


MATERIALS = {
    Material.UNKNOWN:  MaterialProperties("unknown",  0.10, 200,  4000, 0.20, "#888888"),
    Material.CONCRETE: MaterialProperties("concrete", 0.02, 125,   800, 0.05, "#5a5a6a"),
    Material.STONE:    MaterialProperties("stone",    0.03, 100,   600, 0.08, "#7a7a8a"),
    Material.WOOD:     MaterialProperties("wood",     0.10, 400,  2000, 0.15, "#8B6914"),
    Material.GLASS:    MaterialProperties("glass",    0.04, 2000, 8000, 0.03, "#66aacc"),
    Material.METAL:    MaterialProperties("metal",    0.02, 3000, 8000, 0.02, "#aaaacc"),
    Material.FOLIAGE:  MaterialProperties("foliage",  0.50, 300,  3000, 0.60, "#2d8a4e"),
    Material.WATER:    MaterialProperties("water",    0.01, 1000, 8000, 0.10, "#2288aa"),
    Material.FABRIC:   MaterialProperties("fabric",   0.40, 200,  4000, 0.50, "#aa6644"),
    Material.HUMAN:    MaterialProperties("human",    0.30, 300,  2000, 0.40, "#ff9f43"),
}


# ═══════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════

@dataclass
class EchoReturn:
    """Single echo return from a reflecting surface."""
    distance: float         # meters (Equation 1 output)
    azimuth: float          # radians from forward axis
    elevation: float        # radians from horizontal
    amplitude: float        # return amplitude after attenuation
    attenuation: float      # Equation 2 attenuation factor
    material: Material      # classified surface material
    delay: float            # round-trip time (seconds)
    hit_point: np.ndarray = field(default_factory=lambda: np.zeros(3))


@dataclass
class EchoField:
    """Complete echo field from one click event."""
    returns: List[EchoReturn] = field(default_factory=list)
    harmonic_field: float = 0.0
    atmo_factor: float = 1.0
    click_time: float = 0.0
    temperature: float = 20.0
    humidity: float = 50.0
    band_low: float = 0.0    # 125–500 Hz energy
    band_mid: float = 0.0    # 500–2000 Hz energy
    band_high: float = 0.0   # 2000–8000 Hz energy


# ═══════════════════════════════════════════════════════════
# EQUATION 1: ECHO DISTANCE (ToA Ranging)
# d = c · Δτ / 2
# ═══════════════════════════════════════════════════════════

def echo_distance(delay_s: float, temperature_c: float = 20.0) -> float:
    """
    Compute distance from echo delay using Time-of-Arrival.
    
    Identical mathematics to radar/sonar/UWB indoor positioning.
    
    Args:
        delay_s: Round-trip time of flight (seconds)
        temperature_c: Ambient temperature for sound speed correction
    
    Returns:
        One-way distance in meters
    """
    c = 331.3 + 0.606 * temperature_c  # Temperature-corrected
    return c * delay_s / 2.0


# ═══════════════════════════════════════════════════════════
# EQUATION 2: ATMOSPHERIC ATTENUATION
# α(f) = 1.17 × 10⁻⁵ · f²
# ═══════════════════════════════════════════════════════════

def atmospheric_attenuation(freq_hz: float, distance_m: float) -> float:
    """
    Frequency-dependent atmospheric attenuation.
    
    Structurally identical to Friis transmission equation in RF.
    Higher frequencies attenuate faster — materials in high band
    fade before room geometry in low band.
    
    Args:
        freq_hz: Signal frequency
        distance_m: Propagation distance (meters)
    
    Returns:
        Attenuation factor (0.0–1.0, 1.0 = no loss)
    """
    alpha = 1.17e-5 * freq_hz ** 2
    atten_db = alpha * distance_m
    return 10.0 ** (-atten_db / 20.0)


# ═══════════════════════════════════════════════════════════
# EQUATION 3: HARMONIC INTERFERENCE FIELD
# Hᵢ = |Σ Aⱼ · e^(iφⱼ)|
# ═══════════════════════════════════════════════════════════

def harmonic_interference(echoes: List[EchoReturn], freq_hz: float) -> float:
    """
    Compute harmonic interference field from multiple echo sources.
    
    Same mathematics as MIMO beamforming / phased array steering.
    Phase superposition encodes 3D geometry of the space.
    
    Args:
        echoes: List of echo returns with delays and amplitudes
        freq_hz: Frequency to compute interference at
    
    Returns:
        Interference field magnitude
    """
    if not echoes:
        return 0.0
    
    # Hᵢ = |Σ Aⱼ · e^(iφⱼ)|
    complex_sum = 0.0 + 0.0j
    for echo in echoes:
        phase = 2.0 * np.pi * freq_hz * echo.delay
        complex_sum += echo.amplitude * np.exp(1j * phase)
    
    return abs(complex_sum)


def compute_three_band_spectrum(echoes: List[EchoReturn]) -> tuple:
    """
    Compute the three-band acoustic grammar that the brain decodes.
    
    Returns:
        (band_low, band_mid, band_high) — energy in each band
        - Low  (125–500 Hz):  Room geometry / volume
        - Mid  (500–2000 Hz): Crowd density / moving bodies
        - High (2000–8000 Hz): Surface material / texture
    """
    # Low band: geometry
    freqs_low = np.arange(125, 501, 25)
    band_low = np.mean([harmonic_interference(echoes, f) for f in freqs_low])
    
    # Mid band: crowd
    freqs_mid = np.arange(500, 2001, 100)
    band_mid = np.mean([harmonic_interference(echoes, f) for f in freqs_mid])
    
    # High band: material
    freqs_high = np.arange(2000, 8001, 400)
    band_high = np.mean([harmonic_interference(echoes, f) for f in freqs_high])
    
    return band_low, band_mid, band_high


# ═══════════════════════════════════════════════════════════
# EQUATION 4: ENVIRONMENTAL CHANNEL MODEL
# α(f,H) = k · f² · e^(−βH)
# ═══════════════════════════════════════════════════════════

def environmental_channel(freq_hz: float, humidity_pct: float) -> float:
    """
    Humidity-dependent propagation model.
    
    Equivalent to 5G mmWave environmental channel models (ITU-R P.676).
    
    Args:
        freq_hz: Signal frequency
        humidity_pct: Relative humidity (0–100)
    
    Returns:
        Environmental attenuation coefficient
    """
    k = 1.17e-5
    beta = 0.03
    return k * freq_hz ** 2 * np.exp(-beta * humidity_pct)


# ═══════════════════════════════════════════════════════════
# RAY CASTING — Point Cloud → Echo Prediction
# ═══════════════════════════════════════════════════════════

@dataclass
class Obstacle:
    """2D obstacle for simulation (extruded to 3D)."""
    x: float
    y: float
    width: float
    height: float
    material: Material
    label: str


def ray_cast_2d(
    origin: np.ndarray,
    heading: float,
    obstacles: List[Obstacle],
    cone_half_angle: float = np.pi / 3,
    num_rays: int = 48,
    max_range: float = 15.0,
    temperature: float = 20.0,
    humidity: float = 50.0
) -> EchoField:
    """
    Cast acoustic rays and compute complete echo field.
    
    This is the core function: given user position, heading, and obstacles,
    compute what the echoes should sound like.
    
    Args:
        origin: User position [x, y]
        heading: User facing direction (radians)
        obstacles: List of obstacles in the environment
        cone_half_angle: Half-angle of propagation cone
        num_rays: Number of rays to cast
        max_range: Maximum detection range (meters)
        temperature: Ambient temperature (°C)
        humidity: Relative humidity (%)
    
    Returns:
        Complete EchoField with all returns and band energies
    """
    c = 331.3 + 0.606 * temperature
    echo_field = EchoField(temperature=temperature, humidity=humidity)
    
    for i in range(num_rays):
        # Ray angle within cone
        angle = heading - cone_half_angle + \
                (2.0 * cone_half_angle * i / (num_rays - 1))
        
        direction = np.array([np.cos(angle), np.sin(angle)])
        
        # Find nearest intersection
        best_hit = None
        best_dist = max_range
        
        for obs in obstacles:
            # Ray-rectangle intersection
            hit = _ray_rect_intersect(
                origin, direction,
                np.array([obs.x, obs.y]),
                np.array([obs.x + obs.width, obs.y + obs.height])
            )
            
            if hit is not None:
                dist = np.linalg.norm(hit - origin)
                if 0.1 < dist < best_dist:
                    best_dist = dist
                    best_hit = (hit, obs)
        
        if best_hit is not None:
            hit_point, obs = best_hit
            mat_props = MATERIALS[obs.material]
            
            # Equation 1: distance from delay
            delay = 2.0 * best_dist / c
            
            # Equation 2: atmospheric attenuation
            center_freq = (mat_props.freq_low + mat_props.freq_high) / 2.0
            atten = atmospheric_attenuation(center_freq, best_dist)
            
            # Equation 4: environmental correction
            env_atten = environmental_channel(center_freq, humidity)
            
            # Amplitude: inverse-square + absorption + environment
            amplitude = (1.0 - mat_props.absorption) / (best_dist ** 2 + 0.01)
            amplitude *= atten * np.exp(-env_atten * best_dist)
            
            echo = EchoReturn(
                distance=best_dist,
                azimuth=angle - heading,
                elevation=0.0,
                amplitude=amplitude,
                attenuation=atten,
                material=obs.material,
                delay=delay,
                hit_point=hit_point
            )
            echo_field.returns.append(echo)
    
    # Equation 3: compute interference spectrum
    if echo_field.returns:
        echo_field.harmonic_field = harmonic_interference(
            echo_field.returns, 1000.0
        )
        echo_field.band_low, echo_field.band_mid, echo_field.band_high = \
            compute_three_band_spectrum(echo_field.returns)
        echo_field.atmo_factor = environmental_channel(2000.0, humidity)
    
    return echo_field


def _ray_rect_intersect(
    origin: np.ndarray,
    direction: np.ndarray,
    rect_min: np.ndarray,
    rect_max: np.ndarray
) -> Optional[np.ndarray]:
    """Ray-rectangle intersection using slab method."""
    t_near = -np.inf
    t_far = np.inf
    
    for i in range(2):
        if abs(direction[i]) < 1e-8:
            if origin[i] < rect_min[i] or origin[i] > rect_max[i]:
                return None
        else:
            t1 = (rect_min[i] - origin[i]) / direction[i]
            t2 = (rect_max[i] - origin[i]) / direction[i]
            if t1 > t2:
                t1, t2 = t2, t1
            t_near = max(t_near, t1)
            t_far = min(t_far, t2)
            if t_near > t_far or t_far < 0:
                return None
    
    t = t_near if t_near > 0 else t_far
    if t < 0:
        return None
    
    return origin + direction * t


# ═══════════════════════════════════════════════════════════
# MATERIAL CLASSIFICATION FROM ECHO SPECTRUM
# ═══════════════════════════════════════════════════════════

def classify_material(echo_spectrum: np.ndarray, sample_rate: float) -> Material:
    """
    Classify material from echo spectral signature using sub-band energy ratios.
    
    Args:
        echo_spectrum: Magnitude spectrum from FFT
        sample_rate: Sample rate of the spectrum
    
    Returns:
        Classified material type
    """
    n_bins = len(echo_spectrum)
    freq_per_bin = sample_rate / (n_bins * 2)
    
    freqs = np.arange(n_bins) * freq_per_bin
    mag_sq = echo_spectrum ** 2
    
    energy_low = np.sum(mag_sq[freqs < 500])
    energy_mid = np.sum(mag_sq[(freqs >= 500) & (freqs < 2000)])
    energy_high = np.sum(mag_sq[(freqs >= 2000) & (freqs < 8000)])
    
    total = energy_low + energy_mid + energy_high + 1e-10
    r_low = energy_low / total
    r_mid = energy_mid / total
    r_high = energy_high / total
    
    if r_low > 0.6 and r_high < 0.15:
        return Material.CONCRETE if r_low > 0.75 else Material.STONE
    if r_high > 0.5 and r_low < 0.15:
        return Material.METAL if r_high > 0.7 else Material.GLASS
    if r_mid > 0.5:
        if total < 0.3:
            return Material.FOLIAGE
        if total < 0.5:
            return Material.HUMAN
        return Material.WOOD
    if r_high > 0.3 and r_low < 0.3:
        return Material.WATER
    
    return Material.UNKNOWN

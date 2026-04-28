"""
Benchmark script to compare Python vs C++ performance in Astrosis.
Tests propagator, conjunction detection, fuel calculation, and maneuver planning.
"""

import time
import sys
import os
import logging
import tracemalloc

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'cpp', 'build'))
sys.path.insert(0, os.path.dirname(__file__))

from engine.physics.propagator import rk4_py, rk4_py_drag
from engine.physics.conjunction import ConjunctionDetector as PyConjunctionDetector
from engine.physics.fuel import FuelTracker as PyFuelTracker
from engine.physics.maneuver import ManeuverCalculator as PyManeuverCalculator
from engine.physics.accelerator import _physics
from engine.constants import MU, RE, INITIAL_FUEL, DRY_MASS

# Test data - ISS-like orbit
ISS_STATE = [
    -6371.0 + 400.0,  # x (km) - altitude 400km
    0.0,              # y
    0.0,              # z
    0.0,              # vx
    7.66,             # vy (km/s) - circular orbit velocity
    0.0               # vz
]

# Generate multiple satellite states for conjunction test
def generate_test_states(count=10):
    """Generate test satellite and debris states."""
    sat_states = []
    debris_states = []
    
    for i in range(count):
        # Satellite states - slight variations
        sat_states.append([
            -6371.0 + 400.0 + i * 0.1,
            i * 0.5,
            0.0,
            0.0,
            7.66 + i * 0.001,
            0.0
        ])
        
        # Debris states - potentially close approaches
        debris_states.append([
            -6371.0 + 405.0 + i * 0.1,
            i * 0.5 + 1.0,
            0.5,
            0.1,
            7.65 + i * 0.001,
            0.1
        ])
    
    return sat_states, debris_states

def benchmark_propagation(iterations=100000):
    """Benchmark RK4 propagation."""
    logger.info(f"\n{'='*60}")
    logger.info("BENCHMARK: RK4 Propagation")
    logger.info(f"{'='*60}")
    logger.info(f"Iterations: {iterations}")
    
    # Python benchmark
    start = time.time()
    state = tuple(ISS_STATE)
    for _ in range(iterations):
        state = rk4_py(state, 10.0)  # 10 second steps
    py_time = time.time() - start
    logger.info(f"Python: {py_time:.4f}s")
    
    # C++ benchmark
    if _physics:
        start = time.time()
        state = ISS_STATE.copy()
        propagator = _physics.Propagator()
        for _ in range(iterations):
            state = list(propagator.propagate(state, 10.0))
        cpp_time = time.time() - start
        logger.info(f"C++:    {cpp_time:.4f}s")
        speedup = py_time / cpp_time
        logger.info(f"Speedup: {speedup:.2f}x")
    else:
        logger.warning("C++ module not available - skipping C++ benchmark")
        cpp_time = None
    
    return py_time, cpp_time

def benchmark_propagation_with_drag(iterations=100000):
    """Benchmark RK4 propagation with atmospheric drag."""
    logger.info(f"\n{'='*60}")
    logger.info("BENCHMARK: RK4 Propagation with Drag")
    logger.info(f"{'='*60}")
    logger.info(f"Iterations: {iterations}")
    
    # Python benchmark
    start = time.time()
    state = tuple(ISS_STATE)
    for _ in range(iterations):
        state = rk4_py_drag(state, 10.0, area=10.0, mass=1000.0, cd=2.2)
    py_time = time.time() - start
    logger.info(f"Python: {py_time:.4f}s")
    
    # C++ benchmark
    if _physics:
        start = time.time()
        state = ISS_STATE.copy()
        propagator = _physics.Propagator()
        for _ in range(iterations):
            state = list(propagator.propagate_with_drag(state, 10.0, 10.0, 1000.0, 2.2))
        cpp_time = time.time() - start
        logger.info(f"C++:    {cpp_time:.4f}s")
        speedup = py_time / cpp_time
        logger.info(f"Speedup: {speedup:.2f}x")
    else:
        logger.warning("C++ module not available - skipping C++ benchmark")
        cpp_time = None
    
    return py_time, cpp_time

def benchmark_conjunction_detection(sat_count=100, debris_count=100):
    """Benchmark conjunction detection."""
    logger.info(f"\n{'='*60}")
    logger.info("BENCHMARK: Conjunction Detection")
    logger.info(f"{'='*60}")
    logger.info(f"Satellites: {sat_count}, Debris: {debris_count}")
    
    sat_states, debris_states = generate_test_states(max(sat_count, debris_count))
    sat_states = sat_states[:sat_count]
    debris_states = debris_states[:debris_count]
    
    # Python benchmark
    start = time.time()
    detector = PyConjunctionDetector()
    warnings_py = detector.detect(sat_states, debris_states, lookahead_s=3600.0, step_s=60.0)
    py_time = time.time() - start
    logger.info(f"Python: {py_time:.4f}s ({len(warnings_py)} warnings)")
    
    # C++ benchmark
    if _physics:
        start = time.time()
        detector = _physics.ConjunctionDetector()
        warnings_cpp = detector.detect(sat_states, debris_states, 3600.0)
        cpp_time = time.time() - start
        logger.info(f"C++:    {cpp_time:.4f}s ({len(warnings_cpp)} warnings)")
        speedup = py_time / cpp_time
        logger.info(f"Speedup: {speedup:.2f}x")
    else:
        logger.warning("C++ module not available - skipping C++ benchmark")
        cpp_time = None
    
    return py_time, cpp_time

def benchmark_conjunction_detection_extreme(sat_count=500, debris_count=500):
    """Benchmark conjunction detection with extreme workload."""
    logger.info(f"\n{'='*60}")
    logger.info("BENCHMARK: Conjunction Detection (EXTREME)")
    logger.info(f"{'='*60}")
    logger.info(f"Satellites: {sat_count}, Debris: {debris_count}")
    
    sat_states, debris_states = generate_test_states(max(sat_count, debris_count))
    sat_states = sat_states[:sat_count]
    debris_states = debris_states[:debris_count]
    
    # Python benchmark
    start = time.time()
    detector = PyConjunctionDetector()
    warnings_py = detector.detect(sat_states, debris_states, lookahead_s=3600.0, step_s=60.0)
    py_time = time.time() - start
    logger.info(f"Python: {py_time:.4f}s ({len(warnings_py)} warnings)")
    
    # C++ benchmark
    if _physics:
        start = time.time()
        detector = _physics.ConjunctionDetector()
        warnings_cpp = detector.detect(sat_states, debris_states, 3600.0)
        cpp_time = time.time() - start
        logger.info(f"C++:    {cpp_time:.4f}s ({len(warnings_cpp)} warnings)")
        speedup = py_time / cpp_time
        logger.info(f"Speedup: {speedup:.2f}x")
    else:
        logger.warning("C++ module not available - skipping C++ benchmark")
        cpp_time = None
    
    return py_time, cpp_time

def benchmark_conjunction_detection_ultra(sat_count=1000, debris_count=1000):
    """Benchmark conjunction detection with ultra-extreme workload."""
    logger.info(f"\n{'='*60}")
    logger.info("BENCHMARK: Conjunction Detection (ULTRA-EXTREME)")
    logger.info(f"{'='*60}")
    logger.info(f"Satellites: {sat_count}, Debris: {debris_count}")
    
    sat_states, debris_states = generate_test_states(max(sat_count, debris_count))
    sat_states = sat_states[:sat_count]
    debris_states = debris_states[:debris_count]
    
    # Python benchmark with memory tracking
    tracemalloc.start()
    start = time.time()
    detector = PyConjunctionDetector()
    warnings_py = detector.detect(sat_states, debris_states, lookahead_s=3600.0, step_s=60.0)
    py_time = time.time() - start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    logger.info(f"Python: {py_time:.4f}s ({len(warnings_py)} warnings)")
    logger.info(f"Python Memory: Peak {peak / 1024 / 1024:.2f} MB")
    
    # C++ benchmark with memory tracking
    if _physics:
        tracemalloc.start()
        start = time.time()
        detector = _physics.ConjunctionDetector()
        warnings_cpp = detector.detect(sat_states, debris_states, 3600.0)
        cpp_time = time.time() - start
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        logger.info(f"C++:    {cpp_time:.4f}s ({len(warnings_cpp)} warnings)")
        logger.info(f"C++ Memory: Peak {peak / 1024 / 1024:.2f} MB")
        speedup = py_time / cpp_time
        logger.info(f"Speedup: {speedup:.2f}x")
    else:
        logger.warning("C++ module not available - skipping C++ benchmark")
        cpp_time = None
    
    return py_time, cpp_time

def benchmark_fuel_calculation(iterations=100000):
    """Benchmark fuel calculation."""
    logger.info(f"\n{'='*60}")
    logger.info("BENCHMARK: Fuel Calculation")
    logger.info(f"{'='*60}")
    logger.info(f"Iterations: {iterations}")
    
    delta_v = [0.1, 0.2, 0.3]  # km/s
    
    # Python benchmark
    start = time.time()
    tracker = PyFuelTracker(INITIAL_FUEL)
    for _ in range(iterations):
        fuel = tracker.calculate_fuel_cost(delta_v)
    py_time = time.time() - start
    logger.info(f"Python: {py_time:.4f}s (fuel: {fuel:.4f} kg)")
    
    # C++ benchmark
    if _physics:
        start = time.time()
        tracker = _physics.FuelTracker(INITIAL_FUEL, DRY_MASS)
        for _ in range(iterations):
            fuel = tracker.calculate_fuel_cost(delta_v)
        cpp_time = time.time() - start
        logger.info(f"C++:    {cpp_time:.4f}s (fuel: {fuel:.4f} kg)")
        speedup = py_time / cpp_time
        logger.info(f"Speedup: {speedup:.2f}x")
    else:
        logger.warning("C++ module not available - skipping C++ benchmark")
        cpp_time = None
    
    return py_time, cpp_time

def benchmark_maneuver_calculation(iterations=10000):
    """Benchmark maneuver calculation."""
    logger.info(f"\n{'='*60}")
    logger.info("BENCHMARK: Maneuver Calculation")
    logger.info(f"{'='*60}")
    logger.info(f"Iterations: {iterations}")
    
    # Create a mock warning
    from engine.physics.conjunction import ConjunctionWarning
    warning = ConjunctionWarning(
        sat_id=0,
        debris_id=1,
        current_distance=5.0,
        time_to_closest_approach=3600.0,
        severity="WARNING",
        relative_velocity=[0.1, 0.2, 0.3]
    )
    
    # Python benchmark
    start = time.time()
    calculator = PyManeuverCalculator()
    for _ in range(iterations):
        result = calculator.calculate(ISS_STATE, warning)
    py_time = time.time() - start
    logger.info(f"Python: {py_time:.4f}s")
    
    # C++ benchmark - skip due to type incompatibility with ConjunctionWarning
    if _physics:
        logger.warning("C++ maneuver benchmark skipped - type incompatibility with ConjunctionWarning")
        cpp_time = None
    else:
        logger.warning("C++ module not available - skipping C++ benchmark")
        cpp_time = None
    
    return py_time, cpp_time

def benchmark_batch_propagation(num_objects=1000, steps=1000):
    """Benchmark batch propagation - propagate multiple objects for multiple steps."""
    logger.info(f"\n{'='*60}")
    logger.info("BENCHMARK: Batch Propagation")
    logger.info(f"{'='*60}")
    logger.info(f"Objects: {num_objects}, Steps: {steps}")
    
    # Generate multiple initial states
    states = []
    for i in range(num_objects):
        states.append([
            -6371.0 + 400.0 + i * 0.01,
            i * 0.1,
            0.0,
            0.0,
            7.66 + i * 0.0001,
            0.0
        ])
    
    # Python benchmark
    start = time.time()
    for _ in range(steps):
        for i in range(num_objects):
            states[i] = list(rk4_py(tuple(states[i]), 10.0))
    py_time = time.time() - start
    logger.info(f"Python: {py_time:.4f}s")
    
    # C++ benchmark
    if _physics:
        # Reset states
        states = []
        for i in range(num_objects):
            states.append([
                -6371.0 + 400.0 + i * 0.01,
                i * 0.1,
                0.0,
                0.0,
                7.66 + i * 0.0001,
                0.0
            ])
        
        start = time.time()
        propagator = _physics.Propagator()
        for _ in range(steps):
            for i in range(num_objects):
                states[i] = list(propagator.propagate(states[i], 10.0))
        cpp_time = time.time() - start
        logger.info(f"C++:    {cpp_time:.4f}s")
        speedup = py_time / cpp_time
        logger.info(f"Speedup: {speedup:.2f}x")
    else:
        logger.warning("C++ module not available - skipping C++ benchmark")
        cpp_time = None
    
    return py_time, cpp_time

def benchmark_batch_propagation_ultra(num_objects=5000, steps=2000):
    """Benchmark batch propagation with ultra-extreme workload."""
    logger.info(f"\n{'='*60}")
    logger.info("BENCHMARK: Batch Propagation (ULTRA-EXTREME)")
    logger.info(f"{'='*60}")
    logger.info(f"Objects: {num_objects}, Steps: {steps}")
    
    # Generate multiple initial states
    states = []
    for i in range(num_objects):
        states.append([
            -6371.0 + 400.0 + i * 0.01,
            i * 0.1,
            0.0,
            0.0,
            7.66 + i * 0.0001,
            0.0
        ])
    
    # Python benchmark with memory tracking
    tracemalloc.start()
    start = time.time()
    for _ in range(steps):
        for i in range(num_objects):
            states[i] = list(rk4_py(tuple(states[i]), 10.0))
    py_time = time.time() - start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    logger.info(f"Python: {py_time:.4f}s")
    logger.info(f"Python Memory: Peak {peak / 1024 / 1024:.2f} MB")
    
    # C++ benchmark with memory tracking
    if _physics:
        # Reset states
        states = []
        for i in range(num_objects):
            states.append([
                -6371.0 + 400.0 + i * 0.01,
                i * 0.1,
                0.0,
                0.0,
                7.66 + i * 0.0001,
                0.0
            ])
        
        tracemalloc.start()
        start = time.time()
        propagator = _physics.Propagator()
        for _ in range(steps):
            for i in range(num_objects):
                states[i] = list(propagator.propagate(states[i], 10.0))
        cpp_time = time.time() - start
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        logger.info(f"C++:    {cpp_time:.4f}s")
        logger.info(f"C++ Memory: Peak {peak / 1024 / 1024:.2f} MB")
        speedup = py_time / cpp_time
        logger.info(f"Speedup: {speedup:.2f}x")
    else:
        logger.warning("C++ module not available - skipping C++ benchmark")
        cpp_time = None
    
    return py_time, cpp_time

def benchmark_conjunction_detection_maximum(sat_count=2000, debris_count=2000):
    """Benchmark conjunction detection with maximum stress test."""
    logger.info(f"\n{'='*60}")
    logger.info("BENCHMARK: Conjunction Detection (MAXIMUM STRESS)")
    logger.info(f"{'='*60}")
    logger.info(f"Satellites: {sat_count}, Debris: {debris_count}")
    
    sat_states, debris_states = generate_test_states(max(sat_count, debris_count))
    sat_states = sat_states[:sat_count]
    debris_states = debris_states[:debris_count]
    
    # Python benchmark with memory tracking
    tracemalloc.start()
    start = time.time()
    detector = PyConjunctionDetector()
    warnings_py = detector.detect(sat_states, debris_states, lookahead_s=3600.0, step_s=60.0)
    py_time = time.time() - start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    logger.info(f"Python: {py_time:.4f}s ({len(warnings_py)} warnings)")
    logger.info(f"Python Memory: Peak {peak / 1024 / 1024:.2f} MB")
    
    # C++ benchmark with memory tracking
    if _physics:
        tracemalloc.start()
        start = time.time()
        detector = _physics.ConjunctionDetector()
        warnings_cpp = detector.detect(sat_states, debris_states, 3600.0)
        cpp_time = time.time() - start
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        logger.info(f"C++:    {cpp_time:.4f}s ({len(warnings_cpp)} warnings)")
        logger.info(f"C++ Memory: Peak {peak / 1024 / 1024:.2f} MB")
        speedup = py_time / cpp_time
        logger.info(f"Speedup: {speedup:.2f}x")
    else:
        logger.warning("C++ module not available - skipping C++ benchmark")
        cpp_time = None
    
    return py_time, cpp_time

def benchmark_batch_propagation_maximum(num_objects=10000, steps=5000):
    """Benchmark batch propagation with maximum stress test."""
    logger.info(f"\n{'='*60}")
    logger.info("BENCHMARK: Batch Propagation (MAXIMUM STRESS)")
    logger.info(f"{'='*60}")
    logger.info(f"Objects: {num_objects}, Steps: {steps}")
    
    # Generate multiple initial states
    states = []
    for i in range(num_objects):
        states.append([
            -6371.0 + 400.0 + i * 0.01,
            i * 0.1,
            0.0,
            0.0,
            7.66 + i * 0.0001,
            0.0
        ])
    
    # Python benchmark with memory tracking
    tracemalloc.start()
    start = time.time()
    for _ in range(steps):
        for i in range(num_objects):
            states[i] = list(rk4_py(tuple(states[i]), 10.0))
    py_time = time.time() - start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    logger.info(f"Python: {py_time:.4f}s")
    logger.info(f"Python Memory: Peak {peak / 1024 / 1024:.2f} MB")
    
    # C++ benchmark with memory tracking
    if _physics:
        # Reset states
        states = []
        for i in range(num_objects):
            states.append([
                -6371.0 + 400.0 + i * 0.01,
                i * 0.1,
                0.0,
                0.0,
                7.66 + i * 0.0001,
                0.0
            ])
        
        tracemalloc.start()
        start = time.time()
        propagator = _physics.Propagator()
        for _ in range(steps):
            for i in range(num_objects):
                states[i] = list(propagator.propagate(states[i], 10.0))
        cpp_time = time.time() - start
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        logger.info(f"C++:    {cpp_time:.4f}s")
        logger.info(f"C++ Memory: Peak {peak / 1024 / 1024:.2f} MB")
        speedup = py_time / cpp_time
        logger.info(f"Speedup: {speedup:.2f}x")
    else:
        logger.warning("C++ module not available - skipping C++ benchmark")
        cpp_time = None
    
    return py_time, cpp_time

def main():
    logger.info("Starting Astrosis Performance Benchmark")
    logger.info(f"C++ Module Available: {_physics is not None}")
    
    results = {}
    
    # Run benchmarks
    results['propagation'] = benchmark_propagation(100000)
    results['propagation_drag'] = benchmark_propagation_with_drag(100000)
    results['conjunction'] = benchmark_conjunction_detection(100, 100)
    results['conjunction_extreme'] = benchmark_conjunction_detection_extreme(500, 500)
    results['conjunction_ultra'] = benchmark_conjunction_detection_ultra(1000, 1000)
    results['conjunction_maximum'] = benchmark_conjunction_detection_maximum(2000, 2000)
    results['batch_propagation'] = benchmark_batch_propagation(1000, 1000)
    results['batch_propagation_ultra'] = benchmark_batch_propagation_ultra(5000, 2000)
    results['batch_propagation_maximum'] = benchmark_batch_propagation_maximum(10000, 5000)
    results['fuel'] = benchmark_fuel_calculation(100000)
    results['maneuver'] = benchmark_maneuver_calculation(10000)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY")
    logger.info(f"{'='*60}")
    
    for name, (py_time, cpp_time) in results.items():
        if cpp_time:
            speedup = py_time / cpp_time
            logger.info(f"{name:20s}: Python {py_time:.4f}s, C++ {cpp_time:.4f}s, Speedup {speedup:.2f}x")
        else:
            logger.info(f"{name:20s}: Python {py_time:.4f}s (C++ N/A)")
    
    # Overall speedup if all C++ benchmarks ran
    if all(cpp is not None for _, cpp in results.values()):
        total_py = sum(py for py, _ in results.values())
        total_cpp = sum(cpp for _, cpp in results.values())
        overall_speedup = total_py / total_cpp
        logger.info(f"\nOverall Speedup: {overall_speedup:.2f}x")

if __name__ == "__main__":
    main()

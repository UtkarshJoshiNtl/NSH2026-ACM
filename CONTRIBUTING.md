# Contributing

## Development setup

```bash
git clone https://github.com/anomalyco/astrosis.git
cd astrosis
pip install -r requirements.txt
cd cpp && mkdir build && cd build && cmake .. && make -j$(nproc)
```

## Running tests

```bash
python -m pytest tests/test_correctness.py -v
```

## Running validation

```bash
python validation/validate_physics.py
```

## Code style

- Python: PEP 8, 100 char line limit
- C++: Google style, 100 char line limit
- CUDA: Same as C++ with `//` comments for device functions

## What to contribute

- Additional force models (atmospheric drag improvements, higher-order gravity)
- Performance optimisations (warp occupancy tuning, tensor core exploration)
- Additional validation tests
- Bug fixes and numerical stability improvements

Before submitting a PR, ensure:
1. All tests pass
2. C++ builds cleanly with and without CUDA
3. Validation suite produces expected results

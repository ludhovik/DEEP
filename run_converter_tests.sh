#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 tests/test_converter_package.py
python3 tests/test_exterior_tracing.py
python3 tests/test_spectral_truncation.py
python3 tests/test_incremental_conversion.py

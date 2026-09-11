#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 tests/test_converter_package.py
python3 tests/test_magic_graph_compat.py
python3 tests/test_exterior_tracing.py
python3 tests/test_spectral_truncation.py
python3 tests/test_incremental_conversion.py
python3 tests/test_inner_core.py
python3 tests/test_calypso_converter.py
python3 tests/test_calypso_binary.py
python3 tests/test_field_line_performance.py
python3 tests/test_quicc_converter.py
python3 tests/test_quicc_shell.py
python3 tests/test_rayleigh_converter.py

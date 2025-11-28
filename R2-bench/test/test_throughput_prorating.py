"""
Test suite for throughput prorating across phases.
"""

import sys
import os
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from visualizations.throughput_utils import (
    get_phase_boundaries,
    calculate_phase_throughput_with_prorating,
    prorate_bytes_to_time_windows
)


def test_get_phase_boundaries():
    """Test phase boundary extraction."""
    # Create test data with requests in different phases
    data = pd.DataFrame({
        'phase_id': ['ramp_1', 'ramp_1', 'ramp_2', 'ramp_2'],
        'start_ts': [100.0, 105.0, 200.0, 205.0],
        'end_ts': [150.0, 155.0, 250.0, 255.0],
        'bytes': [1000, 2000, 3000, 4000],
        'http_status': [200, 200, 200, 200]
    })
    
    boundaries = get_phase_boundaries(data)
    
    assert 'ramp_1' in boundaries
    assert 'ramp_2' in boundaries
    assert boundaries['ramp_1'] == (100.0, 155.0)  # min start, max end
    assert boundaries['ramp_2'] == (200.0, 255.0)


def test_prorating_single_phase():
    """Test prorating when request stays in single phase."""
    data = pd.DataFrame({
        'phase_id': ['ramp_1'],
        'start_ts': [100.0],
        'end_ts': [200.0],
        'bytes': [1000],
        'http_status': [200]
    })
    
    result = calculate_phase_throughput_with_prorating(data, phase_id='ramp_1')
    
    assert result['total_bytes'] == 1000.0
    assert result['duration_seconds'] == 100.0
    assert result['request_count'] == 1


def test_prorating_across_two_phases():
    """Test prorating when request spans two phases (50% each)."""
    # Phase 1: 100-200, Phase 2: 200-300
    # Request: 150-250 (50% in phase 1, 50% in phase 2)
    data = pd.DataFrame({
        'phase_id': ['ramp_1', 'ramp_2'],  # Request started in ramp_1
        'start_ts': [100.0, 150.0],  # Request starts at 150
        'end_ts': [200.0, 250.0],  # Request ends at 250
        'bytes': [1000, 1000],  # 1000 bytes total
        'http_status': [200, 200]
    })
    
    # Get boundaries
    boundaries = get_phase_boundaries(data)
    
    # Calculate for phase 1 (should get 50% of bytes)
    result1 = calculate_phase_throughput_with_prorating(
        data, phase_id='ramp_1', phase_boundaries=boundaries
    )
    
    # Calculate for phase 2 (should get 50% of bytes)
    result2 = calculate_phase_throughput_with_prorating(
        data, phase_id='ramp_2', phase_boundaries=boundaries
    )
    
    # Request duration: 250 - 150 = 100 seconds
    # Overlap with phase 1: 150-200 = 50 seconds (50%)
    # Overlap with phase 2: 200-250 = 50 seconds (50%)
    
    # Phase 1 should get 50% of 1000 = 500 bytes
    assert abs(result1['total_bytes'] - 500.0) < 0.01
    
    # Phase 2 should get 50% of 1000 = 500 bytes
    assert abs(result2['total_bytes'] - 500.0) < 0.01


def test_prorating_across_three_phases():
    """Test prorating when request spans three phases (30%, 30%, 40%)."""
    # Phase 1: 100-200, Phase 2: 200-300, Phase 3: 300-400
    # Request: 170-370 (30s in phase 1, 30s in phase 2, 40s in phase 3)
    data = pd.DataFrame({
        'phase_id': ['ramp_1', 'ramp_2', 'ramp_3'],
        'start_ts': [100.0, 170.0, 300.0],  # Request starts at 170
        'end_ts': [200.0, 370.0, 400.0],  # Request ends at 370
        'bytes': [1000, 1000, 1000],  # 1000 bytes total
        'http_status': [200, 200, 200]
    })
    
    boundaries = get_phase_boundaries(data)
    
    # Request duration: 370 - 170 = 200 seconds
    # Overlap with phase 1: 170-200 = 30 seconds (15%)
    # Overlap with phase 2: 200-300 = 100 seconds (50%)
    # Overlap with phase 3: 300-370 = 70 seconds (35%)
    
    result1 = calculate_phase_throughput_with_prorating(
        data, phase_id='ramp_1', phase_boundaries=boundaries
    )
    result2 = calculate_phase_throughput_with_prorating(
        data, phase_id='ramp_2', phase_boundaries=boundaries
    )
    result3 = calculate_phase_throughput_with_prorating(
        data, phase_id='ramp_3', phase_boundaries=boundaries
    )
    
    # Phase 1: 30/200 * 1000 = 150 bytes
    assert abs(result1['total_bytes'] - 150.0) < 0.01
    
    # Phase 2: 100/200 * 1000 = 500 bytes
    assert abs(result2['total_bytes'] - 500.0) < 0.01
    
    # Phase 3: 70/200 * 1000 = 350 bytes
    assert abs(result3['total_bytes'] - 350.0) < 0.01
    
    # Total should sum to 1000
    total = result1['total_bytes'] + result2['total_bytes'] + result3['total_bytes']
    assert abs(total - 1000.0) < 0.01


def test_prorating_time_windows():
    """Test prorating bytes across time windows."""
    # Request: 100-200 (100 seconds), 1000 bytes
    data = pd.DataFrame({
        'phase_id': ['ramp_1'],
        'start_ts': [100.0],
        'end_ts': [200.0],
        'bytes': [1000],
        'http_status': [200]
    })
    
    # Create 1-second windows from 100 to 200
    window_times = list(range(100, 201))
    
    result = prorate_bytes_to_time_windows(
        data,
        window_times,
        window_size_seconds=1.0
    )
    
    # Should have 100 windows (100-199, each 1 second)
    assert len(result) == 100
    
    # Each window should have 1/100 of the bytes = 10 bytes
    # Throughput per second in megabits per second (Mbps): (10 bytes * BITS_PER_BYTE) / MEGABITS_PER_MB = 0.00008 Mbps
    assert all(abs(row['total_bytes'] - 10.0) < 0.01 for _, row in result.iterrows())


def test_multiple_requests_same_phase():
    """Test prorating with multiple requests in the same phase."""
    data = pd.DataFrame({
        'phase_id': ['ramp_1', 'ramp_1'],
        'start_ts': [100.0, 150.0],
        'end_ts': [200.0, 250.0],
        'bytes': [1000, 2000],
        'http_status': [200, 200]
    })
    
    result = calculate_phase_throughput_with_prorating(data, phase_id='ramp_1')
    
    # Both requests fully in phase 1, so total bytes = 1000 + 2000 = 3000
    assert result['total_bytes'] == 3000.0
    assert result['request_count'] == 2


def test_request_partially_overlapping_phase():
    """Test request that only partially overlaps with a phase."""
    # Phase 1: 100-200
    # Request: 150-250 (50% in phase 1, 50% outside)
    data = pd.DataFrame({
        'phase_id': ['ramp_1', 'ramp_2'],
        'start_ts': [100.0, 150.0],
        'end_ts': [200.0, 250.0],
        'bytes': [1000, 1000],
        'http_status': [200, 200]
    })
    
    boundaries = get_phase_boundaries(data)
    result = calculate_phase_throughput_with_prorating(
        data, phase_id='ramp_1', phase_boundaries=boundaries
    )
    
    # Request duration: 250 - 150 = 100 seconds
    # Overlap with phase 1: 150-200 = 50 seconds (50%)
    # Phase 1 should get 50% of 1000 = 500 bytes
    assert abs(result['total_bytes'] - 500.0) < 0.01


def run_tests():
    """Run all tests."""
    tests = [
        ("get_phase_boundaries", test_get_phase_boundaries),
        ("prorating_single_phase", test_prorating_single_phase),
        ("prorating_across_two_phases", test_prorating_across_two_phases),
        ("prorating_across_three_phases", test_prorating_across_three_phases),
        ("prorating_time_windows", test_prorating_time_windows),
        ("multiple_requests_same_phase", test_multiple_requests_same_phase),
        ("request_partially_overlapping_phase", test_request_partially_overlapping_phase),
    ]
    
    print("=" * 70)
    print("THROUGHPUT PRORATING TESTS")
    print("=" * 70 + "\n")
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            print(f"✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {name}: {type(e).__name__}: {e}")
            failed += 1
    
    print(f"\n{'=' * 70}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)


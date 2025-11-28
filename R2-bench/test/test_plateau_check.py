"""Test suite for plateau detection algorithm."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

from algorithms.plateau_check import PlateauCheck
from configuration import PLATEAU_THRESHOLD


def assert_condition(condition, message="Assertion failed"):
    """Simple assertion helper for running tests without pytest."""
    if not condition:
        raise AssertionError(message)


class TestPlateauDetection:
    """Test cases for plateau detection logic."""
    
    def test_no_measurements(self):
        """Should return False when no measurements."""
        plateau = PlateauCheck()
        result, reason = plateau.is_plateau_reached()
        assert result is False
        assert "Not enough measurements" in reason
    
    def test_one_measurement(self):
        """Should return False with only one measurement."""
        plateau = PlateauCheck()
        plateau.add_measurement(8, 100, 5)
        result, reason = plateau.is_plateau_reached()
        assert result is False
        assert "Not enough measurements" in reason
    
    def test_two_measurements(self):
        """Should return False with two measurements."""
        plateau = PlateauCheck()
        plateau.add_measurement(8, 100, 5)
        plateau.add_measurement(16, 120, 5)
        result, reason = plateau.is_plateau_reached()
        assert result is False
        assert "Not enough measurements for plateau detection" in reason
    
    def test_system_bandwidth_limit(self):
        """Should stop when system bandwidth limit is reached."""
        plateau = PlateauCheck(system_bandwidth_gbps=5)
        plateau.add_measurement(8, 100, 5)
        plateau.add_measurement(16, 6000, 5)  # Exceeds limit
        
        result, reason = plateau.is_plateau_reached()
        assert result is True
        assert "System bandwidth limit reached" in reason
    
    def test_clean_improvement(self):
        """Should continue when throughput is clearly improving."""
        plateau = PlateauCheck()
        plateau.add_measurement(8, 100, 5)
        plateau.add_measurement(16, 120, 5)  # +20%
        plateau.add_measurement(24, 140, 5)  # +16.7%
        
        result, reason = plateau.is_plateau_reached()
        assert result is False
        assert "still improving" in reason
    
    def test_complete_plateau(self):
        """Should detect when throughput is completely stable."""
        plateau = PlateauCheck()
        plateau.add_measurement(8, 140, 5)
        plateau.add_measurement(16, 140, 5)  # 0%
        plateau.add_measurement(24, 140, 5)  # 0%
        
        result, reason = plateau.is_plateau_reached()
        assert result is True
        assert "improvement below" in reason.lower()
    
    def test_small_improvements(self):
        """Should detect plateau with small improvements."""
        plateau = PlateauCheck()
        plateau.add_measurement(8, 100, 5)
        plateau.add_measurement(16, 105, 5)  # +5%
        plateau.add_measurement(24, 108, 5)  # +2.9%
        
        result, reason = plateau.is_plateau_reached()
        assert result is True
        assert "improvement below" in reason.lower()
    
    def test_mixed_small_changes(self):
        """Should detect plateau with mixed small changes."""
        plateau = PlateauCheck()
        plateau.add_measurement(8, 100, 5)
        plateau.add_measurement(16, 103, 5)  # +3%
        plateau.add_measurement(24, 101, 5)  # -2%
        
        result, reason = plateau.is_plateau_reached()
        assert result is True
    
    def test_degradation_from_peak(self):
        """Should stop when throughput drops significantly from peak."""
        plateau = PlateauCheck()
        plateau.add_measurement(8, 100, 5)
        plateau.add_measurement(16, 150, 5)  # Peak
        plateau.add_measurement(24, 100, 5)  # Drops 33% from peak
        
        result, reason = plateau.is_plateau_reached()
        assert result is True
        assert "degradation from peak" in reason.lower()
        assert "150.0" in reason
        assert "100.0" in reason
    
    def test_severe_degradation(self):
        """Should stop on severe single-step degradation."""
        plateau = PlateauCheck()
        plateau.add_measurement(8, 100, 5)
        plateau.add_measurement(16, 150, 5)
        plateau.add_measurement(24, 50, 5)  # -66% drop
        
        result, reason = plateau.is_plateau_reached()
        assert result is True
        assert "severe degradation" in reason.lower() or "degradation from peak" in reason.lower()
    
    def test_gradual_decline(self):
        """Should stop when throughput consistently declines."""
        plateau = PlateauCheck()
        plateau.add_measurement(8, 140, 5)
        plateau.add_measurement(16, 120, 5)  # -14.3%
        plateau.add_measurement(24, 100, 5)  # -16.7%
        
        result, reason = plateau.is_plateau_reached()
        # Should either detect degradation from peak or consistent decline
        assert result is True
    
    def test_custom_threshold(self):
        """Should respect custom threshold parameter."""
        plateau = PlateauCheck(threshold=0.05)  # 5% threshold
        
        # Small changes that pass 10% threshold but fail 5%
        plateau.add_measurement(8, 100, 5)
        plateau.add_measurement(16, 108, 5)  # +8%
        plateau.add_measurement(24, 115, 5)  # +6.5%
        
        result, reason = plateau.is_plateau_reached()
        # With 5% threshold, +8% and +6.5% don't trigger plateau
        assert result is False
    
    def test_summary_no_measurements(self):
        """Should return correct summary with no measurements."""
        plateau = PlateauCheck()
        summary = plateau.get_plateau_summary()
        
        assert summary['status'] == 'no_measurements'
    
    def test_summary_with_measurements(self):
        """Should return correct summary with measurements."""
        plateau = PlateauCheck()
        plateau.add_measurement(8, 100, 5)
        plateau.add_measurement(16, 120, 5)
        plateau.add_measurement(24, 140, 5)
        
        summary = plateau.get_plateau_summary()
        
        assert summary['measurements_count'] == 3
        assert 'plateau_reached' in summary
        assert 'reason' in summary
        assert summary['last_measurement']['concurrency'] == 24
        assert summary['last_measurement']['throughput_gbps'] == 140
    
    def test_peak_is_first_measurement(self):
        """Should handle case where first measurement is the peak."""
        plateau = PlateauCheck()
        plateau.add_measurement(8, 150, 5)  # Peak
        plateau.add_measurement(16, 140, 5)  # -6.7%
        plateau.add_measurement(24, 120, 5)  # -14.3%
        
        result, reason = plateau.is_plateau_reached()
        # Should detect degradation (120 is 20% below 150)
        assert result is True
        assert "degradation from peak" in reason.lower()
    
    def test_spike_then_plateau(self):
        """Should handle temporary spike followed by plateau."""
        plateau = PlateauCheck()
        plateau.add_measurement(8, 100, 5)
        plateau.add_measurement(16, 200, 5)  # Spike
        plateau.add_measurement(24, 105, 5)  # Below spike but above initial
        
        result, reason = plateau.is_plateau_reached()
        # Should detect degradation from peak of 200
        assert result is True
        assert "degradation from peak" in reason.lower()


def run_examples():
    """Run examples to demonstrate plateau detection flow."""
    print("\n" + "="*70)
    print("PLATEAU DETECTION EXAMPLES")
    print("="*70)
    
    examples = [
        ("Clean Improvement", [
            (8, 100), (16, 120), (24, 140)
        ]),
        ("Small Improvements", [
            (8, 100), (16, 105), (24, 108)
        ]),
        ("Complete Plateau", [
            (8, 140), (16, 140), (24, 140)
        ]),
        ("Degradation from Peak", [
            (8, 100), (16, 150), (24, 100)
        ]),
        ("Mixed Small Changes", [
            (8, 100), (16, 103), (24, 101)
        ]),
    ]
    
    for name, measurements in examples:
        print(f"\n{'-'*70}")
        print(f"Example: {name}")
        print(f"{'-'*70}")
        
        plateau = PlateauCheck()
        
        for i, (concurrency, throughput) in enumerate(measurements):
            plateau.add_measurement(concurrency, throughput, 5)
            is_plateau, reason = plateau.is_plateau_reached()
            
            if i == 0:
                print(f"  Step {i+1}: {concurrency} conn -> {throughput} Gbps")
            else:
                prev_throughput = measurements[i-1][1]
                change = ((throughput - prev_throughput) / prev_throughput) * 100
                print(f"  Step {i+1}: {concurrency} conn -> {throughput} Gbps ({change:+.1f}%)")
            
            if is_plateau:
                print(f"  ✓ PLATEAU REACHED: {reason}")
                print(f"  -> Test would stop here\n")
                break
            else:
                print(f"  → Continuing: {reason}")


if __name__ == "__main__":
    # Run examples
    run_examples()
    
    # Run basic tests
    print("\n" + "="*70)
    print("Running basic test suite...")
    print("="*70 + "\n")
    
    try:
        test = TestPlateauDetection()
        
        tests = [
            ("test_no_measurements", test.test_no_measurements),
            ("test_clean_improvement", test.test_clean_improvement),
            ("test_complete_plateau", test.test_complete_plateau),
            ("test_degradation_from_peak", test.test_degradation_from_peak),
        ]
        
        for name, test_func in tests:
            try:
                test_func()
                print(f"✓ {name}")
            except AssertionError as e:
                print(f"✗ {name}: {e}")
            except Exception as e:
                print(f"✗ {name}: {type(e).__name__}: {e}")
        
        print("\nBasic tests complete!")
        
    except Exception as e:
        print(f"Error running tests: {e}")
    
    if HAS_PYTEST:
        print("\n" + "="*70)
        print("Running full test suite with pytest...")
        print("="*70 + "\n")
        pytest.main([__file__, "-v"])


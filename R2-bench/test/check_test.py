"""
Basic tests for the check functionality.
"""

import unittest
import sys
import os
import time
from unittest.mock import Mock, MagicMock

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithms.plateu_check import PlateauCheck
from algorithms.warm_up import WarmUp
from algorithms.ramp import Ramp
from configuration import PLATEAU_THRESHOLD


class TestCheckFunctionality(unittest.TestCase):
    """Test basic check functionality."""
    
    def test_plateau_checker(self):
        """Test plateau checker basic functionality."""
        checker = PlateauCheck(threshold=PLATEAU_THRESHOLD)
        
        # Test initial state
        self.assertEqual(len(checker.measurements), 0)
        
        # Test adding measurements - use values that should create a plateau
        # All improvements should be below 5% threshold
        checker.add_measurement(8, 100.0, 300)
        checker.add_measurement(16, 101.0, 300)  # 1% improvement (below threshold)
        checker.add_measurement(24, 101.5, 300)  # 0.5% improvement (below threshold)
        
        self.assertEqual(len(checker.measurements), 3)
        
        # Test plateau detection
        plateau_reached, reason = checker.is_plateau_reached()
        self.assertTrue(plateau_reached)
        self.assertIn("threshold", reason)
    
    def test_plateau_summary(self):
        """Test plateau summary generation."""
        checker = PlateauCheck()
        checker.add_measurement(8, 100.0, 300)
        
        summary = checker.get_plateau_summary()
        self.assertIn('measurements_count', summary)
        self.assertIn('plateau_reached', summary)
    
    def test_concurrent_warm_up(self):
        """Test concurrent warm-up functionality."""
        # Mock storage system
        mock_storage = Mock()
        mock_storage.download_range.return_value = (b'test_data' * 1000, 50.0)  # 1KB data, 50ms latency
        
        # Test with short duration for testing
        warm_up = WarmUp(mock_storage, warm_up_minutes=0.01, concurrency=2)  # 0.6 seconds
        
        results = warm_up.execute()
        
        # Verify results structure
        self.assertIn('concurrency', results)
        self.assertIn('total_requests', results)
        self.assertIn('successful_requests', results)
        self.assertIn('success_rate', results)
        self.assertIn('total_bytes_downloaded', results)
        self.assertIn('avg_latency_ms', results)
        self.assertIn('errors', results)
        
        # Verify concurrency
        self.assertEqual(results['concurrency'], 2)
        
        # Verify some requests were made
        self.assertGreater(results['total_requests'], 0)
        self.assertGreater(results['successful_requests'], 0)
        
        # Verify success rate is reasonable
        self.assertGreaterEqual(results['success_rate'], 0.0)
        self.assertLessEqual(results['success_rate'], 1.0)
    
    def test_ramp_with_plateau_detection(self):
        """Test ramp algorithm with plateau detection."""
        # Mock storage system
        mock_storage = Mock()
        mock_storage.download_range.return_value = (b'test_data' * 1000, 50.0)  # 1KB data, 50ms latency
        
        # Test with short duration for testing
        ramp = Ramp(mock_storage, initial_concurrency=2, ramp_step=2, 
                         step_duration_minutes=0.01, plateau_threshold=0.1)  # 0.6 seconds per step
        
        results = ramp.find_optimal_concurrency(max_concurrency=10)
        
        # Verify results structure
        self.assertIn('best_concurrency', results)
        self.assertIn('best_throughput_mbps', results)
        self.assertIn('step_results', results)
        self.assertIn('plateau_detected', results)
        self.assertIn('plateau_reason', results)
        self.assertIn('plateau_summary', results)
        
        # Verify some steps were executed
        self.assertGreater(len(results['step_results']), 0)
        
        # Verify plateau detection fields exist
        self.assertIsInstance(results['plateau_detected'], bool)
        self.assertIsInstance(results['plateau_reason'], str)


if __name__ == '__main__':
    unittest.main()

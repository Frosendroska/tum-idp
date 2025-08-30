"""
Basic tests for the check functionality.
"""

import unittest
import sys
import os

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithms.plateu_check import SimplePlateauCheck


class TestCheckFunctionality(unittest.TestCase):
    """Test basic check functionality."""
    
    def test_plateau_checker(self):
        """Test plateau checker basic functionality."""
        checker = SimplePlateauCheck(threshold=0.05)
        
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
        checker = SimplePlateauCheck()
        checker.add_measurement(8, 100.0, 300)
        
        summary = checker.get_plateau_summary()
        self.assertIn('measurements_count', summary)
        self.assertIn('plateau_reached', summary)


if __name__ == '__main__':
    unittest.main()

"""
Basic tests for the R2 benchmark components.
"""

import unittest
import tempfile
import os
import sys

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from configuration import OBJECT_SIZE_GB, RANGE_SIZE_MB
from persistence.base import BenchmarkRecord, SimpleMetricsCollector


class TestBenchmarkComponents(unittest.TestCase):
    """Test basic benchmark components."""
    
    def test_configuration(self):
        """Test configuration constants."""
        self.assertIsInstance(OBJECT_SIZE_GB, int)
        self.assertIsInstance(RANGE_SIZE_MB, int)
        self.assertGreater(OBJECT_SIZE_GB, 0)
        self.assertGreater(RANGE_SIZE_MB, 0)
    
    def test_benchmark_record(self):
        """Test BenchmarkRecord creation."""
        record = BenchmarkRecord(
            thread_id=1,
            conn_id=1,
            object_key="test-object",
            range_start=0,
            range_len=1024,
            bytes_downloaded=1024,
            latency_ms=100.0,
            http_status=200,
            concurrency=8
        )
        
        self.assertEqual(record.thread_id, 1)
        self.assertEqual(record.conn_id, 1)
        self.assertEqual(record.object_key, "test-object")
        self.assertEqual(record.bytes, 1024)
        self.assertEqual(record.http_status, 200)
        self.assertEqual(record.concurrency, 8)
    
    def test_metrics_collector(self):
        """Test SimpleMetricsCollector functionality."""
        collector = SimpleMetricsCollector()
        
        # Test adding records
        record = BenchmarkRecord(
            thread_id=1,
            conn_id=1,
            object_key="test-object",
            range_start=0,
            range_len=1024,
            bytes_downloaded=1024,
            latency_ms=100.0,
            http_status=200,
            concurrency=8
        )
        
        collector.add_record(record)
        self.assertEqual(len(collector.records), 1)
        
        # Test summary generation
        summary = collector.get_summary()
        self.assertIn('total_requests', summary)
        self.assertIn('successful_requests', summary)
        self.assertEqual(summary['total_requests'], 1)
        self.assertEqual(summary['successful_requests'], 1)


if __name__ == '__main__':
    unittest.main()


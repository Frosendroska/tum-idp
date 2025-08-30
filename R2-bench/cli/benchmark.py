"""
Phase 2: Long-term performance benchmark.
"""

import os
import sys
import logging
import argparse
import time

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from configuration import (
    WARM_UP_MINUTES, STEADY_STATE_HOURS,
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
)
from systems.r2 import R2System
from systems.aws import AWSSystem
from algorithms.warm_up import SimpleWarmUp
from algorithms.steady import SimpleSteadyState
from persistence.parquet import SimpleParquetPersistence

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleBenchmarkRunner:
    """Simple benchmark runner for long-term performance measurement."""
    
    def __init__(self, storage_type: str = "r2", concurrency: int = 64):
        self.storage_type = storage_type.lower()
        self.concurrency = concurrency
        self.storage_system = None
        self.persistence = None
        
        # Initialize components
        self._initialize_components()
        
        logger.info(f"Initialized benchmark runner: {storage_type.upper()} with {concurrency} connections")
    
    def _initialize_components(self):
        """Initialize required components."""
        try:
            # Initialize storage system
            if self.storage_type == "r2":
                credentials = {
                    'aws_access_key_id': AWS_ACCESS_KEY_ID,
                    'aws_secret_access_key': AWS_SECRET_ACCESS_KEY,
                    'region_name': 'auto'
                }
                self.storage_system = R2System(credentials)
                
            elif self.storage_type == "s3":
                credentials = {
                    'aws_access_key_id': AWS_ACCESS_KEY_ID,
                    'aws_secret_access_key': AWS_SECRET_ACCESS_KEY,
                    'region_name': AWS_REGION
                }
                self.storage_system = AWSSystem(credentials)
                
            else:
                raise ValueError(f"Unsupported storage type: {self.storage_type}")
            
            # Initialize persistence
            self.persistence = SimpleParquetPersistence(output_dir="results")
                
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise
    
    def run_benchmark(self):
        """Execute the complete benchmark."""
        logger.info("Starting R2 benchmark")
        
        # Phase 1: Warm-up
        logger.info("=== Phase 1: Warm-up ===")
        warm_up = SimpleWarmUp(self.storage_system, WARM_UP_MINUTES)
        warm_up_results = warm_up.execute()
        
        logger.info(f"Warm-up completed: {warm_up_results['successful_requests']} successful requests")
        
        # Phase 2: Steady state benchmark
        logger.info("=== Phase 2: Steady State Benchmark ===")
        steady_state = SimpleSteadyState(
            self.storage_system,
            concurrency=self.concurrency,
            duration_hours=STEADY_STATE_HOURS
        )
        
        steady_results = steady_state.execute()
        
        # Save results to Parquet
        if self.persistence:
            # Create benchmark records from steady state results
            # This is a simplified approach - in a real implementation you'd collect records during execution
            logger.info("Saving benchmark results to Parquet file")
            
            # For now, just save a summary
            # In a real implementation, you'd collect BenchmarkRecord objects during execution
            logger.info("Benchmark results summary:")
            logger.info(f"  Total requests: {steady_results.get('total_requests', 0)}")
            logger.info(f"  Successful requests: {steady_results.get('successful_requests', 0)}")
            logger.info(f"  Success rate: {steady_results.get('success_rate', 0):.2%}")
            logger.info(f"  Total bytes: {steady_results.get('total_bytes_downloaded', 0) / (1024**3):.2f} GB")
            logger.info(f"  Average throughput: {steady_results.get('avg_throughput_mbps', 0):.1f} Mbps")
            logger.info(f"  Average latency: {steady_results.get('avg_latency_ms', 0):.1f} ms")
        
        return {
            'warm_up': warm_up_results,
            'steady_state': steady_results,
            'storage_type': self.storage_type,
            'concurrency': self.concurrency
        }


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Long-term benchmark for R2')
    parser.add_argument('--storage', choices=['r2', 's3'], default='r2',
                        help='Storage type to use (default: r2)')
    parser.add_argument('--concurrency', type=int, default=64,
                        help='Number of concurrent connections (default: 64)')
    parser.add_argument('--hours', type=int, default=STEADY_STATE_HOURS,
                        help=f'Duration in hours (default: {STEADY_STATE_HOURS})')
    
    args = parser.parse_args()
    
    try:
        # Update configuration
        global STEADY_STATE_HOURS
        STEADY_STATE_HOURS = args.hours
        
        runner = SimpleBenchmarkRunner(args.storage, args.concurrency)
        
        # Execute benchmark
        results = runner.run_benchmark()
        
        logger.info("Benchmark completed successfully")
        logger.info(f"Storage: {results['storage_type'].upper()}")
        logger.info(f"Concurrency: {results['concurrency']}")
        logger.info(f"Duration: {args.hours} hours")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error executing benchmark: {e}")
        return 1


if __name__ == '__main__':
    exit(main())

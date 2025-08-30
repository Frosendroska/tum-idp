"""
Phase 1: Capacity discovery and plateau detection.
"""

import os
import sys
import logging
import argparse
import time

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from configuration import WARM_UP_MINUTES, RAMP_STEP_MINUTES, RAMP_STEP_CONCURRENCY
from systems.r2 import R2System
from systems.aws import AWSSystem
from algorithms.warm_up import SimpleWarmUp
from algorithms.ramp import SimpleRamp

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleCapacityChecker:
    """Simple capacity checker for finding optimal concurrency."""
    
    def __init__(self, storage_type: str = "r2"):
        self.storage_type = storage_type.lower()
        self.storage_system = None
        
        # Initialize storage system
        self._initialize_storage()
        
        logger.info(f"Initialized capacity checker for {storage_type.upper()}")
    
    def _initialize_storage(self):
        """Initialize the appropriate storage system."""
        try:
            if self.storage_type == "r2":
                credentials = {
                    'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
                    'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
                    'region_name': 'auto'
                }
                self.storage_system = R2System(credentials)
                
            elif self.storage_type == "s3":
                credentials = {
                    'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
                    'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
                    'region_name': os.getenv('AWS_REGION', 'eu-central-1')
                }
                self.storage_system = AWSSystem(credentials)
                
            else:
                raise ValueError(f"Unsupported storage type: {self.storage_type}")
                
        except Exception as e:
            logger.error(f"Failed to initialize {self.storage_type.upper()} storage: {e}")
            raise
    
    def check_capacity(self):
        """Execute the capacity discovery process."""
        logger.info("Starting capacity discovery process")
        
        # Phase 1: Warm-up
        logger.info("=== Phase 1: Warm-up ===")
        warm_up = SimpleWarmUp(self.storage_system, WARM_UP_MINUTES)
        warm_up_results = warm_up.execute()
        
        logger.info(f"Warm-up completed: {warm_up_results['successful_requests']} successful requests")
        
        # Phase 2: Ramp-up to find optimal concurrency
        logger.info("=== Phase 2: Ramp-up ===")
        ramp = SimpleRamp(
            self.storage_system,
            initial_concurrency=RAMP_STEP_CONCURRENCY,
            ramp_step=RAMP_STEP_CONCURRENCY,
            step_duration_minutes=RAMP_STEP_MINUTES
        )
        
        ramp_results = ramp.find_optimal_concurrency(max_concurrency=100)
        
        # Report results
        logger.info("=== Capacity Discovery Results ===")
        logger.info(f"Best concurrency: {ramp_results['best_concurrency']}")
        logger.info(f"Best throughput: {ramp_results['best_throughput_mbps']:.1f} Mbps")
        logger.info(f"Steps completed: {len(ramp_results['step_results'])}")
        
        # Show step-by-step results
        for i, step in enumerate(ramp_results['step_results']):
            logger.info(f"Step {i+1}: {step['concurrency']} conn -> {step['throughput_mbps']:.1f} Mbps")
        
        return {
            'warm_up': warm_up_results,
            'ramp_up': ramp_results,
            'optimal_concurrency': ramp_results['best_concurrency'],
            'max_throughput_mbps': ramp_results['best_throughput_mbps']
        }


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Capacity discovery for R2 benchmark')
    parser.add_argument('--storage', choices=['r2', 's3'], default='r2',
                        help='Storage type to use (default: r2)')
    
    args = parser.parse_args()
    
    try:
        checker = SimpleCapacityChecker(args.storage)
        
        # Execute capacity discovery
        results = checker.check_capacity()
        
        logger.info("Capacity discovery completed successfully")
        logger.info(f"Optimal concurrency: {results['optimal_concurrency']}")
        logger.info(f"Maximum throughput: {results['max_throughput_mbps']:.1f} Mbps")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error executing capacity discovery: {e}")
        return 1


if __name__ == '__main__':
    exit(main())

"""
Phase 1: Capacity discovery and plateau detection.
"""

import os
import sys
import logging
import argparse
import time

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from configuration import (
    WARM_UP_MINUTES, INITIAL_CONCURRENCY, RAMP_STEP_SECONDS, RAMP_STEP_CONCURRENCY,
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, DEFAULT_OBJECT_KEY, WORKER_BANDWIDTH_MBPS,
    MAX_CONCURRENCY
)
from systems.r2 import R2System
from systems.aws import AWSSystem
from algorithms.warm_up import WarmUp
from algorithms.ramp import Ramp

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CapacityChecker:
    """Simple capacity checker for finding optimal concurrency."""
    
    def __init__(self, storage_type: str = "r2", object_key: str = None, worker_bandwidth_mbps: float = None):
        self.storage_type = storage_type.lower()
        self.object_key = object_key or DEFAULT_OBJECT_KEY
        self.worker_bandwidth_mbps = worker_bandwidth_mbps if worker_bandwidth_mbps is not None else WORKER_BANDWIDTH_MBPS
        self.storage_system = None
        
        # Initialize storage system
        self._initialize_storage()
        
        logger.info(f"Initialized capacity checker for {storage_type.upper()} with worker bandwidth limit: {self.worker_bandwidth_mbps} Mbps")
    
    def _initialize_storage(self):
        """Initialize the appropriate storage system."""
        try:
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
                
        except Exception as e:
            logger.error(f"Failed to initialize {self.storage_type.upper()} storage: {e}")
            raise
    
    def check_capacity(self, object_key: str = None):
        """Execute the capacity discovery process."""
        if object_key:
            self.object_key = object_key
        logger.info("Starting capacity discovery process")
        logger.info(f"Using object key: {self.object_key}")
        
        # Check if object exists
        try:
            logger.info("Checking if test object exists...")
            # Try to get object metadata
            response = self.storage_system.client.head_object(Bucket=self.storage_system.bucket_name, Key=self.object_key)
            logger.info(f"Test object found: {response['ContentLength']} bytes")
        except Exception as e:
            logger.error(f"Test object not found or error accessing it: {e}")
            logger.error("Please run 'python cli.py upload --storage r2' first to create the test object")
            raise
        
        # Phase 1: Warm-up
        logger.info("=== Phase 1: Concurrent Warm-up ===")
        warm_up = WarmUp(self.storage_system, WARM_UP_MINUTES, INITIAL_CONCURRENCY, self.object_key)
        warm_up_results = warm_up.execute()
        
        logger.info(f"Concurrent warm-up completed: {warm_up_results['successful_requests']} successful requests with {warm_up_results['concurrency']} connections")
        
        # Phase 2: Ramp-up to find optimal concurrency
        logger.info("=== Phase 2: Ramp-up ===")
        logger.info(f"Starting ramp: {INITIAL_CONCURRENCY} -> {MAX_CONCURRENCY}, step {RAMP_STEP_CONCURRENCY} every {RAMP_STEP_SECONDS}s")
        
        try:
            ramp = Ramp(
                self.storage_system,
                initial_concurrency=INITIAL_CONCURRENCY,
                ramp_step=RAMP_STEP_CONCURRENCY,
                step_duration_seconds=RAMP_STEP_SECONDS,  # Use seconds directly
                object_key=self.object_key,
                worker_bandwidth_mbps=self.worker_bandwidth_mbps,
            )
            
            logger.info("Ramp object created successfully, starting optimization...")
            logger.info("Press Ctrl+C to terminate the benchmark gracefully")
            ramp_results = ramp.find_optimal_concurrency(max_concurrency=MAX_CONCURRENCY)
            logger.info("Ramp optimization completed successfully")
            
        except KeyboardInterrupt:
            logger.info("Benchmark interrupted by user (Ctrl+C)")
            logger.info("Gracefully terminating...")
            return {
                'warm_up': warm_up_results,
                'ramp_up': {'error': 'Interrupted by user'},
                'optimal_concurrency': 0,
                'max_throughput_mbps': 0,
                'plateau_detected': False,
                'plateau_reason': 'Interrupted by user'
            }
        except Exception as e:
            logger.error(f"Error during ramp phase: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        
        # Report results
        logger.info("=== Capacity Discovery Results ===")
        logger.info(f"Best concurrency: {ramp_results['best_concurrency']}")
        logger.info(f"Best throughput: {ramp_results['best_throughput_mbps']:.1f} Mbps")
        logger.info(f"Steps completed: {len(ramp_results['step_results'])}")
        logger.info(f"Plateau detected: {ramp_results['plateau_detected']}")
        logger.info(f"Plateau reason: {ramp_results['plateau_reason']}")
        
        # Show step-by-step results
        for i, step in enumerate(ramp_results['step_results']):
            logger.info(f"Step {i+1}: {step['concurrency']} conn -> {step['throughput_mbps']:.1f} Mbps")
        
        # Report parquet file location
        if ramp_results.get('parquet_file'):
            logger.info(f"Detailed results saved to: {ramp_results['parquet_file']}")
            logger.info("Use 'python cli.py visualize --parquet-file <file>' to generate plots")
        
        return {
            'warm_up': warm_up_results,
            'ramp_up': ramp_results,
            'optimal_concurrency': ramp_results['best_concurrency'],
            'max_throughput_mbps': ramp_results['best_throughput_mbps'],
            'plateau_detected': ramp_results['plateau_detected'],
            'plateau_reason': ramp_results['plateau_reason']
        }

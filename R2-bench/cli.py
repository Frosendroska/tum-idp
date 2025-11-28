


import os
import sys
import logging
import argparse
import asyncio

# Required: Use uvloop for better performance
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from configuration import (
    OBJECT_SIZE_GB, STEADY_STATE_HOURS, DEFAULT_OBJECT_KEY,
    DEFAULT_PLOTS_DIR, SYSTEM_BANDWIDTH_GBPS
)

# Set up logging (only if not already configured)
if not logging.root.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleR2BenchmarkCLI:
    """Simple CLI interface for R2 benchmark experiment."""
    
    def __init__(self):
        self.parser = self._create_parser()
    
    def _create_parser(self):
        """Create the main argument parser."""
        parser = argparse.ArgumentParser(
            description='R2 Benchmark Experiment CLI',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Phase 0: Upload test objects to R2
  python cli.py upload --storage r2 --size 1
  
  # Phase 1: Capacity discovery (stops at plateau or worker bandwidth limit)
  python cli.py check --storage r2 --worker-bandwidth 1000
  
  # Phase 2: Long-term benchmark with 64 connections for 3 hours
  python cli.py benchmark --storage r2 --concurrency 64 --hours 3
  
  # Generate plots from benchmark results
  python cli.py visualize --parquet-file results/benchmark_20241201_120000.parquet --output-dir plots
            """
        )
        
        subparsers = parser.add_subparsers(dest='command', help='Available commands')
        
        # Upload command
        upload_parser = subparsers.add_parser('upload', help='Upload test objects')
        upload_parser.add_argument('--storage', choices=['r2', 's3'], default='r2',
                                 help='Storage type to use (default: r2)')
        upload_parser.add_argument('--size', type=int, default=OBJECT_SIZE_GB,
                                 help=f'Object size in GB (default: {OBJECT_SIZE_GB})')
        upload_parser.add_argument('--object-key', type=str, default=DEFAULT_OBJECT_KEY,
                                 help=f'Object key for the test object (default: {DEFAULT_OBJECT_KEY})')
        
        # Check command
        check_parser = subparsers.add_parser('check', help='Capacity discovery')
        check_parser.add_argument('--storage', choices=['r2', 's3'], default='r2',
                                help='Storage type to use (default: r2)')
        check_parser.add_argument('--object-key', type=str, default=DEFAULT_OBJECT_KEY,
                                help=f'Object key for the test object (default: {DEFAULT_OBJECT_KEY})')
        check_parser.add_argument('--system-bandwidth', type=float, default=SYSTEM_BANDWIDTH_GBPS,
                                help=f'Maximum total system bandwidth in Gbps (0 = disabled, default: {SYSTEM_BANDWIDTH_GBPS})')
        
        # Benchmark command
        benchmark_parser = subparsers.add_parser('benchmark', help='Long-term benchmark')
        benchmark_parser.add_argument('--storage', choices=['r2', 's3'], default='r2',
                                    help='Storage type to use (default: r2)')
        benchmark_parser.add_argument('--hours', type=int, default=STEADY_STATE_HOURS,
                                    help=f'Duration in hours (default: {STEADY_STATE_HOURS})')
        benchmark_parser.add_argument('--object-key', type=str, default=DEFAULT_OBJECT_KEY,
                                    help=f'Object key for the test object (default: {DEFAULT_OBJECT_KEY})')
        
        # Visualize command
        visualize_parser = subparsers.add_parser('visualize', help='Generate plots from benchmark results')
        visualize_parser.add_argument('--parquet-file', type=str, required=True,
                                    help='Path to the Parquet file containing benchmark data')
        visualize_parser.add_argument('--output-dir', type=str, default=DEFAULT_PLOTS_DIR,
                                    help=f'Output directory for generated plots (default: {DEFAULT_PLOTS_DIR})')
        
        return parser
    
    async def run_upload(self, args):
        """Run the upload phase."""
        try:
            from cli.uploader import Uploader
            
            logger.info("=== Upload Test Objects ===")
            
            uploader = Uploader(args.storage)
            success = await uploader.upload_test_object(args.size, args.object_key)
            
            if success:
                logger.info("Upload phase completed successfully")
                return 0
            else:
                logger.error("Upload phase failed")
                return 1
                
        except Exception as e:
            logger.error(f"Error in upload phase: {e}")
            return 1
    
    async def run_check(self, args):
        """Run the capacity check phase."""
        try:
            from cli.check import CapacityChecker
            
            logger.info("=== Capacity Discovery ===")
            
            checker = CapacityChecker(args.storage, args.object_key, args.system_bandwidth)
            results = await checker.check_capacity(args.object_key)
            
            logger.info("Capacity check completed successfully")
            return 0
            
        except Exception as e:
            logger.error(f"Error in capacity check phase: {e}")
            return 1
    
    async def run_benchmark(self, args):
        """Run the benchmark phase."""
        try:
            from cli.benchmark import BenchmarkRunner
            
            logger.info("=== Long-term Benchmark ===")
            
            runner = BenchmarkRunner(
                storage_type=args.storage,
                concurrency=args.concurrency,
                object_key=args.object_key
            )
            
            # Execute benchmark
            results = await runner.run_benchmark()
            
            logger.info("Benchmark phase completed successfully")
            return 0
            
        except Exception as e:
            logger.error(f"Error in benchmark phase: {e}")
            return 1
    
    def run_visualize(self, args):
        """Run the visualization phase."""
        try:
            from cli.visualiser import BenchmarkVisualizer
            
            logger.info("=== Visualization Phase ===")
            
            # Check if parquet file exists
            if not os.path.exists(args.parquet_file):
                logger.error(f"Parquet file not found: {args.parquet_file}")
                return 1
            
            # Initialize visualizer
            visualizer = BenchmarkVisualizer(args.parquet_file, args.output_dir)
            
            # Create all plots
            plots = visualizer.create_all_plots()
            
            if plots:
                logger.info(f"Successfully created {len(plots)} plots in {args.output_dir}")
                for plot in plots:
                    logger.info(f"  - {plot}")
                return 0
            else:
                logger.error("No plots were created")
                return 1
            
        except Exception as e:
            logger.error(f"Error in visualization phase: {e}")
            return 1
    
    def run(self, args=None):
        """Run the CLI with the given arguments."""
        if args is None:
            args = sys.argv[1:]
        
        parsed_args = self.parser.parse_args(args)
        
        if not parsed_args.command:
            self.parser.print_help()
            return 1
        
        try:
            if parsed_args.command == 'upload':
                return asyncio.run(self.run_upload(parsed_args))
            elif parsed_args.command == 'check':
                return asyncio.run(self.run_check(parsed_args))
            elif parsed_args.command == 'benchmark':
                return asyncio.run(self.run_benchmark(parsed_args))
            elif parsed_args.command == 'visualize':
                return self.run_visualize(parsed_args)
            else:
                logger.error(f"Unknown command: {parsed_args.command}")
                return 1
                
        except KeyboardInterrupt:
            logger.info("Operation interrupted by user")
            return 1
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return 1


def main():
    """Main entry point."""
    cli = SimpleR2BenchmarkCLI()
    exit(cli.run())


if __name__ == '__main__':
    main()

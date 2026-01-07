


import os
import sys
import logging
import argparse
import asyncio

# Required: Use uvloop for better performance
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# This file is at the project root, so imports work directly
# No sys.path manipulation needed

from configuration import (
    OBJECT_SIZE_GB, DEFAULT_OBJECT_KEY,
    DEFAULT_PLOTS_DIR
)
from common.instance_detector import InstanceDetector

# Set up logging (only if not already configured)
if not logging.root.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleR2BenchmarkCLI:
    """Simple CLI interface for R2 benchmark experiment."""

    def __init__(self):
        self.parser = self._create_parser()

    @staticmethod
    def _get_available_instance_types():
        """Get list of available instance types from instance profiles."""
        detector = InstanceDetector()
        return list(detector.profiles.keys())
    
    def _create_parser(self):
        """Create the main argument parser."""
        parser = argparse.ArgumentParser(
            description='R2 Benchmark Experiment CLI',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Phase 0: Upload test objects to R2
  python cli.py upload --storage r2 --size 1

  # Phase 1: Capacity discovery on r5.xlarge instance
  python cli.py check --storage r2 --instance-type r5.xlarge

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
        check_parser.add_argument('--instance-type', type=str, required=True,
                                choices=self._get_available_instance_types(),
                                help=f'EC2 instance type')

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

            checker = CapacityChecker(args.storage, args.object_key)
            results = await checker.check_capacity(args.object_key)

            logger.info("Capacity check completed successfully")
            return 0

        except Exception as e:
            logger.error(f"Error in capacity check phase: {e}")
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

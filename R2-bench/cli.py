


import os
import sys
import logging
import argparse

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from configuration import OBJECT_SIZE_GB, STEADY_STATE_HOURS

# Set up logging
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
  
  # Phase 1: Capacity discovery
  python cli.py check --storage r2
  
  # Phase 2: Long-term benchmark with 64 connections for 3 hours
  python cli.py benchmark --storage r2 --concurrency 64 --hours 3
            """
        )
        
        subparsers = parser.add_subparsers(dest='command', help='Available commands')
        
        # Upload command
        upload_parser = subparsers.add_parser('upload', help='Upload test objects (Phase 0)')
        upload_parser.add_argument('--storage', choices=['r2', 's3'], default='r2',
                                 help='Storage type to use (default: r2)')
        upload_parser.add_argument('--size', type=int, default=OBJECT_SIZE_GB,
                                 help=f'Object size in GB (default: {OBJECT_SIZE_GB})')
        
        # Check command
        check_parser = subparsers.add_parser('check', help='Capacity discovery (Phase 1)')
        check_parser.add_argument('--storage', choices=['r2', 's3'], default='r2',
                                help='Storage type to use (default: r2)')
        
        # Benchmark command
        benchmark_parser = subparsers.add_parser('benchmark', help='Long-term benchmark (Phase 2)')
        benchmark_parser.add_argument('--storage', choices=['r2', 's3'], default='r2',
                                    help='Storage type to use (default: r2)')
        benchmark_parser.add_argument('--concurrency', type=int, default=64,
                                    help='Number of concurrent connections (default: 64)')
        benchmark_parser.add_argument('--hours', type=int, default=STEADY_STATE_HOURS,
                                    help=f'Duration in hours (default: {STEADY_STATE_HOURS})')
        
        return parser
    
    def run_upload(self, args):
        """Run the upload phase."""
        try:
            from cli.uploader import SimpleUploader
            
            logger.info("=== Phase 0: Upload Test Objects ===")
            
            uploader = SimpleUploader(args.storage)
            success = uploader.upload_test_object(args.size)
            
            if success:
                logger.info("Upload phase completed successfully")
                return 0
            else:
                logger.error("Upload phase failed")
                return 1
                
        except Exception as e:
            logger.error(f"Error in upload phase: {e}")
            return 1
    
    def run_check(self, args):
        """Run the capacity check phase."""
        try:
            from cli.check import SimpleCapacityChecker
            
            logger.info("=== Phase 1: Capacity Discovery ===")
            
            checker = SimpleCapacityChecker(args.storage)
            results = checker.check_capacity()
            
            logger.info("Capacity check completed successfully")
            return 0
            
        except Exception as e:
            logger.error(f"Error in capacity check phase: {e}")
            return 1
    
    def run_benchmark(self, args):
        """Run the benchmark phase."""
        try:
            from cli.benchmark import SimpleBenchmarkRunner
            
            logger.info("=== Phase 2: Long-term Benchmark ===")
            
            runner = SimpleBenchmarkRunner(
                storage_type=args.storage,
                concurrency=args.concurrency
            )
            
            # Execute benchmark
            results = runner.run_benchmark()
            
            logger.info("Benchmark phase completed successfully")
            return 0
            
        except Exception as e:
            logger.error(f"Error in benchmark phase: {e}")
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
                return self.run_upload(parsed_args)
            elif parsed_args.command == 'check':
                return self.run_check(parsed_args)
            elif parsed_args.command == 'benchmark':
                return self.run_benchmark(parsed_args)
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

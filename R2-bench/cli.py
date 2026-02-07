#!/usr/bin/env python3
"""
Main CLI entry point for R2 benchmark experiment.

Hybrid multiprocessing + async architecture.
"""

import os
import sys
import logging
import argparse
import asyncio

# Required: Use uvloop for better performance
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from configuration import (
    OBJECT_SIZE_GB,
    DEFAULT_OBJECT_KEY,
    DEFAULT_PLOTS_DIR,
)

# Set up logging
if not logging.root.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class R2BenchmarkCLI:
    """CLI interface for R2 benchmark experiment."""

    def __init__(self):
        self.parser = self._create_parser()

    def _create_parser(self):
        """Create the main argument parser."""
        parser = argparse.ArgumentParser(
            description='R2 Benchmark Experiment CLI (Hybrid Multiprocessing + Async)',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Upload test objects to R2
  python cli.py upload --storage r2 --size 9

  # Capacity discovery (hybrid multiprocessing + async)
  python cli.py check --storage r2

  # Custom configuration
  python cli.py check --storage r2 --processes 12 --workers 80

  # Generate plots from benchmark results
  python cli.py visualize --parquet-file results/capacity_check_r2_20260118.parquet --output-dir plots
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

        # Check command (capacity discovery)
        check_parser = subparsers.add_parser('check', help='Capacity discovery (hybrid multiprocessing + async)')
        check_parser.add_argument('--storage', choices=['r2', 's3'], default='r2',
                                help='Storage type to use (default: r2)')
        check_parser.add_argument('--object-key', type=str, default=DEFAULT_OBJECT_KEY,
                                help=f'Object key for the test object (default: {DEFAULT_OBJECT_KEY})')
        check_parser.add_argument('--bandwidth', type=float, default=50.0,
                                help='System bandwidth limit in Gbps (default: 50.0)')
        check_parser.add_argument('--processes', type=int,
                                help='Number of worker processes (default: auto-detect CPU count)')
        check_parser.add_argument('--workers', type=int,
                                help='Initial workers per core (default: from config)')
        check_parser.add_argument('--ramp-step-workers', type=int,
                                help='Workers to add per core each ramp step (default: from config)')
        check_parser.add_argument('--ramp-step-minutes', type=int,
                                help='Duration of each ramp step in minutes (default: from config)')
        check_parser.add_argument('--pipeline-depth', type=int,
                                help='HTTP requests per worker (default: from config)')
        check_parser.add_argument('--max-workers', type=int,
                                help='Maximum workers per core (default: from config)')

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
                logger.info("✓ Upload phase completed successfully")
                return 0
            else:
                logger.error("✗ Upload phase failed")
                return 1

        except Exception as e:
            logger.error(f"Upload failed: {e}", exc_info=True)
            return 1

    async def run_check(self, args):
        """Run capacity discovery phase."""
        try:
            from cli.check import CapacityChecker

            logger.info("=== Capacity Discovery (Hybrid Multiprocessing + Async) ===")

            checker = CapacityChecker(
                storage_type=args.storage,
                object_key=args.object_key,
                system_bandwidth_gbps=args.bandwidth,
                num_processes=args.processes if hasattr(args, 'processes') and args.processes else None,
                workers_per_process=args.workers if hasattr(args, 'workers') and args.workers else None,
                ramp_step_workers=args.ramp_step_workers if hasattr(args, 'ramp_step_workers') and args.ramp_step_workers else None,
                ramp_step_minutes=args.ramp_step_minutes if hasattr(args, 'ramp_step_minutes') and args.ramp_step_minutes else None,
                pipeline_depth=args.pipeline_depth if hasattr(args, 'pipeline_depth') and args.pipeline_depth else None,
                max_workers_per_core=args.max_workers if hasattr(args, 'max_workers') and args.max_workers else None,
            )

            await checker.check_capacity()

            logger.info("✓ Capacity discovery completed successfully")
            return 0

        except Exception as e:
            logger.error(f"Capacity discovery failed: {e}", exc_info=True)
            return 1

    def run_visualize(self, args):
        """Generate plots from benchmark results."""
        try:
            from cli.visualiser import BenchmarkVisualizer

            logger.info("=== Generate Plots ===")

            visualizer = BenchmarkVisualizer(
                parquet_file=args.parquet_file,
                output_dir=args.output_dir
            )

            visualizer.create_all_plots()

            logger.info("✓ Visualization completed successfully")
            return 0

        except Exception as e:
            logger.error(f"Visualization failed: {e}", exc_info=True)
            return 1

    def run(self):
        """Parse arguments and run the appropriate command."""
        args = self.parser.parse_args()

        if not args.command:
            self.parser.print_help()
            return 1

        if args.command == 'upload':
            return asyncio.run(self.run_upload(args))
        elif args.command == 'check':
            return asyncio.run(self.run_check(args))
        elif args.command == 'visualize':
            return self.run_visualize(args)
        else:
            logger.error(f"Unknown command: {args.command}")
            self.parser.print_help()
            return 1


def main():
    """Main entry point."""
    cli = R2BenchmarkCLI()
    exit_code = cli.run()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()

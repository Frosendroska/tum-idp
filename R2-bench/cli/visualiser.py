"""
Simple standalone visualizer for R2 benchmark results.
"""

import os
import sys
import logging
import argparse

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from visualization.visualiser import SimpleBenchmarkVisualizer

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Visualize R2 benchmark results')
    parser.add_argument('parquet_file', help='Path to Parquet file with benchmark data')
    parser.add_argument('--output-dir', default='plots',
                        help='Output directory for plots (default: plots)')
    parser.add_argument('--plot-type', 
                        choices=['all', 'throughput', 'latency', 'errors', 'summary'],
                        default='all',
                        help='Type of plot to create (default: all)')
    
    args = parser.parse_args()
    
    try:
        logger.info("=== Visualization Phase ===")
        
        visualizer = SimpleBenchmarkVisualizer(args.parquet_file, args.output_dir)
        
        if args.plot_type == 'all':
            plots = visualizer.create_all_plots()
        else:
            plots = []
            if args.plot_type == 'throughput':
                plots.append(visualizer.create_throughput_timeline())
            elif args.plot_type == 'latency':
                plots.append(visualizer.create_latency_distribution())
            elif args.plot_type == 'errors':
                plots.append(visualizer.create_error_analysis())
            elif args.plot_type == 'summary':
                plots.append(visualizer.create_summary_report())
        
        # Filter out empty results
        plots = [p for p in plots if p]
        
        if plots:
            logger.info(f"Successfully created {len(plots)} visualization files:")
            for plot in plots:
                logger.info(f"  - {plot}")
            return 0
        else:
            logger.warning("No plots were created")
            return 1
            
    except Exception as e:
        logger.error(f"Error in visualization phase: {e}")
        return 1


if __name__ == '__main__':
    exit(main())

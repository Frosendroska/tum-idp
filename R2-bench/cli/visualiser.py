"""
Visualization orchestrator for R2 benchmark results.

This module provides a simple CLI interface for creating visualizations from
benchmark results stored in Parquet format.
"""

import pandas as pd
import os
import logging

# Import modular plot classes
from visualizations.throughput_plots import ThroughputPlotter
from visualizations.latency_plots import LatencyPlotter
from visualizations.dashboard import DashboardPlotter

logger = logging.getLogger(__name__)


class BenchmarkVisualizer:
    """Simple visualizer for benchmark results using modular plot classes."""
    
    def __init__(self, parquet_file: str, output_dir: str = "plots"):
        self.parquet_file = parquet_file
        self.output_dir = output_dir
        self.data = None
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Load data
        self._load_data()
        
        # Initialize modular plotters
        if self.data is not None:
            self.throughput_plotter = ThroughputPlotter(self.data, self.output_dir)
            self.latency_plotter = LatencyPlotter(self.data, self.output_dir)
            self.dashboard_plotter = DashboardPlotter(self.data, self.output_dir)
        else:
            self.throughput_plotter = None
            self.latency_plotter = None
            self.dashboard_plotter = None
        
        logger.info(f"Initialized visualizer for {parquet_file}")
    
    def _load_data(self):
        """Load benchmark data from Parquet file."""
        try:
            self.data = pd.read_parquet(self.parquet_file)
            logger.info(f"Loaded {len(self.data)} records from {self.parquet_file}")
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            self.data = None
    
    # Throughput plot methods
    def create_throughput_timeline(self):
        """Create throughput timeline plot with phase information."""
        if self.throughput_plotter is None:
            logger.warning("Throughput plotter not available")
            return None
        return self.throughput_plotter.create_throughput_timeline()
    
    def create_per_second_throughput_timeline(self):
        """Create per-second throughput timeline using sweep line algorithm."""
        if self.throughput_plotter is None:
            logger.warning("Throughput plotter not available")
            return None
        return self.throughput_plotter.create_per_second_throughput_timeline()
    
    def create_throughput_vs_concurrency(self):
        """Create throughput vs concurrency analysis plot."""
        if self.throughput_plotter is None:
            logger.warning("Throughput plotter not available")
            return None
        return self.throughput_plotter.create_throughput_vs_concurrency()
    
    def create_throughput_stats_table(self):
        """Create throughput statistics table by phase/step."""
        if self.throughput_plotter is None:
            logger.warning("Throughput plotter not available")
            return None
        return self.throughput_plotter.create_throughput_stats_table()
    
    # Latency plot methods
    def create_latency_histogram(self):
        """Create comprehensive latency histogram plot with multiple views."""
        if self.latency_plotter is None:
            logger.warning("Latency plotter not available")
            return None
        return self.latency_plotter.create_latency_histogram()
    
    def create_latency_boxplot(self):
        """Create latency box plot by concurrency."""
        if self.latency_plotter is None:
            logger.warning("Latency plotter not available")
            return None
        return self.latency_plotter.create_latency_boxplot()
    
    def create_latency_scatter(self):
        """Create latency vs concurrency scatter plot."""
        if self.latency_plotter is None:
            logger.warning("Latency plotter not available")
            return None
        return self.latency_plotter.create_latency_scatter()
    
    def create_latency_stats_table(self):
        """Create latency statistics table."""
        if self.latency_plotter is None:
            logger.warning("Latency plotter not available")
            return None
        return self.latency_plotter.create_latency_stats_table()
    
    def create_latency_over_time(self):
        """Create latency over time plot."""
        if self.latency_plotter is None:
            logger.warning("Latency plotter not available")
            return None
        return self.latency_plotter.create_latency_over_time()
    
    def create_violin_plot(self):
        """Create violin plot for latency distribution by concurrency."""
        if self.latency_plotter is None:
            logger.warning("Latency plotter not available")
            return None
        return self.latency_plotter.create_violin_plot()
    
    def create_error_analysis(self):
        """Create error analysis plot."""
        if self.latency_plotter is None:
            logger.warning("Latency plotter not available")
            return None
        return self.latency_plotter.create_error_analysis()
    
    # Dashboard methods
    def create_summary_report(self):
        """Create a summary report."""
        if self.dashboard_plotter is None:
            logger.warning("Dashboard plotter not available")
            return None
        return self.dashboard_plotter.create_summary_report()
    
    def create_performance_dashboard(self):
        """Create a comprehensive performance dashboard."""
        if self.dashboard_plotter is None:
            logger.warning("Dashboard plotter not available")
            return None
        return self.dashboard_plotter.create_performance_dashboard()
    
    def create_all_plots(self):
        """Create all available plots."""
        plots = []
        
        # Throughput plots
        if self.throughput_plotter is not None:
            plots.append(self.create_throughput_timeline())
            plots.append(self.create_per_second_throughput_timeline())
            plots.append(self.create_throughput_vs_concurrency())
            plots.append(self.create_throughput_stats_table())
        
        # Latency plots
        if self.latency_plotter is not None:
            plots.append(self.create_latency_histogram())
            plots.append(self.create_latency_boxplot())
            plots.append(self.create_latency_scatter())
            plots.append(self.create_latency_over_time())
            plots.append(self.create_violin_plot())
            plots.append(self.create_latency_stats_table())
            plots.append(self.create_error_analysis())
        
        # Dashboard and summary
        if self.dashboard_plotter is not None:
            plots.append(self.create_performance_dashboard())
            plots.append(self.create_summary_report())
        
        # Filter out None values
        plots = [p for p in plots if p is not None]
        
        logger.info(f"Created {len(plots)} plots and tables in {self.output_dir}")
        return plots

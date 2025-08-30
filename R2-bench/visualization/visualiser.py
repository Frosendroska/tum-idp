"""
Simple visualization for R2 benchmark results.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import logging

logger = logging.getLogger(__name__)


class SimpleBenchmarkVisualizer:
    """Simple visualizer for benchmark results."""
    
    def __init__(self, parquet_file: str, output_dir: str = "plots"):
        self.parquet_file = parquet_file
        self.output_dir = output_dir
        self.data = None
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Load data
        self._load_data()
        
        logger.info(f"Initialized visualizer for {parquet_file}")
    
    def _load_data(self):
        """Load benchmark data from Parquet file."""
        try:
            self.data = pd.read_parquet(self.parquet_file)
            logger.info(f"Loaded {len(self.data)} records from {self.parquet_file}")
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            self.data = None
    
    def create_throughput_timeline(self):
        """Create throughput timeline plot."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for throughput plot")
            return None
        
        try:
            plt.figure(figsize=(12, 6))
            
            # Convert timestamp to datetime
            self.data['datetime'] = pd.to_datetime(self.data['ts'], unit='s')
            
            # Group by time windows and calculate throughput
            self.data['time_window'] = self.data['datetime'].dt.floor('1min')
            throughput_data = self.data.groupby('time_window').agg({
                'bytes': 'sum',
                'latency_ms': 'mean'
            }).reset_index()
            
            # Calculate throughput in Mbps
            throughput_data['throughput_mbps'] = (throughput_data['bytes'] * 8) / (60 * 1_000_000)
            
            # Plot throughput over time
            plt.plot(throughput_data['time_window'], throughput_data['throughput_mbps'], 
                    marker='o', linewidth=2, markersize=4)
            plt.title('Throughput Timeline')
            plt.xlabel('Time')
            plt.ylabel('Throughput (Mbps)')
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            # Save plot
            output_file = os.path.join(self.output_dir, 'throughput_timeline.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Created throughput timeline plot: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create throughput plot: {e}")
            return None
    
    def create_latency_distribution(self):
        """Create latency distribution plot."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for latency plot")
            return None
        
        try:
            plt.figure(figsize=(12, 6))
            
            # Filter successful requests
            successful_data = self.data[self.data['http_status'] == 200]
            
            if len(successful_data) == 0:
                logger.warning("No successful requests for latency plot")
                return None
            
            # Create subplots
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
            
            # Histogram
            ax1.hist(successful_data['latency_ms'], bins=50, alpha=0.7, edgecolor='black')
            ax1.set_title('Latency Distribution (Histogram)')
            ax1.set_xlabel('Latency (ms)')
            ax1.set_ylabel('Frequency')
            ax1.grid(True, alpha=0.3)
            
            # Box plot
            ax2.boxplot(successful_data['latency_ms'])
            ax2.set_title('Latency Distribution (Box Plot)')
            ax2.set_ylabel('Latency (ms)')
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Save plot
            output_file = os.path.join(self.output_dir, 'latency_distribution.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Created latency distribution plot: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create latency plot: {e}")
            return None
    
    def create_error_analysis(self):
        """Create error analysis plot."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for error analysis")
            return None
        
        try:
            plt.figure(figsize=(10, 6))
            
            # Count HTTP status codes
            status_counts = self.data['http_status'].value_counts()
            
            # Create bar plot
            plt.bar(status_counts.index.astype(str), status_counts.values, alpha=0.7)
            plt.title('HTTP Status Code Distribution')
            plt.xlabel('HTTP Status Code')
            plt.ylabel('Count')
            plt.grid(True, alpha=0.3)
            
            # Add value labels on bars
            for i, v in enumerate(status_counts.values):
                plt.text(i, v + max(status_counts.values) * 0.01, str(v), 
                        ha='center', va='bottom')
            
            plt.tight_layout()
            
            # Save plot
            output_file = os.path.join(self.output_dir, 'error_analysis.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Created error analysis plot: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create error analysis plot: {e}")
            return None
    
    def create_summary_report(self):
        """Create a summary report."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for summary report")
            return None
        
        try:
            # Calculate summary statistics
            total_requests = len(self.data)
            successful_requests = len(self.data[self.data['http_status'] == 200])
            success_rate = successful_requests / total_requests if total_requests > 0 else 0
            
            total_bytes = self.data[self.data['http_status'] == 200]['bytes'].sum()
            
            # Calculate time range
            start_time = self.data['ts'].min()
            end_time = self.data['ts'].max()
            duration = end_time - start_time
            
            # Calculate throughput
            throughput_mbps = (total_bytes * 8) / (duration * 1_000_000) if duration > 0 else 0
            
            # Calculate latency statistics
            successful_data = self.data[self.data['http_status'] == 200]
            if len(successful_data) > 0:
                avg_latency = successful_data['latency_ms'].mean()
                p50_latency = successful_data['latency_ms'].quantile(0.5)
                p95_latency = successful_data['latency_ms'].quantile(0.95)
                p99_latency = successful_data['latency_ms'].quantile(0.99)
            else:
                avg_latency = p50_latency = p95_latency = p99_latency = 0
            
            # Create summary text
            summary = f"""
R2 Benchmark Summary Report
===========================

Data Source: {self.parquet_file}
Total Records: {total_requests:,}
Successful Requests: {successful_requests:,}
Success Rate: {success_rate:.2%}

Duration: {duration/3600:.2f} hours
Total Data: {total_bytes/(1024**3):.2f} GB
Average Throughput: {throughput_mbps:.1f} Mbps

Latency Statistics (ms):
  Average: {avg_latency:.1f}
  P50: {p50_latency:.1f}
  P95: {p95_latency:.1f}
  P99: {p99_latency:.1f}

Concurrency Levels: {sorted(self.data['concurrency'].unique())}
            """
            
            # Save summary to file
            output_file = os.path.join(self.output_dir, 'summary_report.txt')
            with open(output_file, 'w') as f:
                f.write(summary)
            
            logger.info(f"Created summary report: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create summary report: {e}")
            return None
    
    def create_all_plots(self):
        """Create all available plots."""
        plots = []
        
        plots.append(self.create_throughput_timeline())
        plots.append(self.create_latency_distribution())
        plots.append(self.create_error_analysis())
        plots.append(self.create_summary_report())
        
        # Filter out None values
        plots = [p for p in plots if p is not None]
        
        logger.info(f"Created {len(plots)} plots in {self.output_dir}")
        return plots

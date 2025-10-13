"""
Simple visualization for R2 benchmark results.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import logging

logger = logging.getLogger(__name__)


class BenchmarkVisualizer:
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
        """Create throughput timeline plot with phase information."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for throughput plot")
            return None
        
        try:
            plt.figure(figsize=(15, 8))
            
            # Convert timestamp to datetime
            self.data['datetime'] = pd.to_datetime(self.data['ts'], unit='s')
            
            # Group by time windows and calculate throughput
            self.data['time_window'] = self.data['datetime'].dt.floor('30s')  # 30-second windows for better granularity
            throughput_data = self.data.groupby('time_window').agg({
                'bytes': 'sum',
                'latency_ms': 'mean',
                'phase_id': 'first'  # Get the phase_id for this time window
            }).reset_index()
            
            # Calculate throughput in Mbps
            throughput_data['throughput_mbps'] = (throughput_data['bytes'] * 8) / (30 * 1_000_000)  # 30-second windows
            
            # Get unique phases for coloring
            phases = self.data['phase_id'].unique()
            phase_colors = plt.cm.Set1(range(len(phases)))
            phase_color_map = dict(zip(phases, phase_colors))
            
            # Plot throughput over time with phase colors
            for phase in phases:
                phase_data = throughput_data[throughput_data['phase_id'] == phase]
                if len(phase_data) > 0:
                    plt.plot(phase_data['time_window'], phase_data['throughput_mbps'], 
                            marker='o', linewidth=2, markersize=4, 
                            color=phase_color_map[phase], label=f'Phase: {phase}')
            
            plt.title('Throughput Timeline by Phase', fontsize=14)
            plt.xlabel('Time', fontsize=12)
            plt.ylabel('Throughput (Mbps)', fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.legend()
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

    def create_per_second_throughput_timeline(self):
        """Create per-second throughput timeline using sweep line algorithm."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for per-second throughput plot")
            return None
        
        try:
            plt.figure(figsize=(15, 8))
            
            # Convert timestamp to datetime
            self.data['datetime'] = pd.to_datetime(self.data['ts'], unit='s')
            
            # Use sweep line algorithm for per-second throughput calculation
            per_second_data = self._calculate_per_second_throughput_sweep_line()
            
            if per_second_data is None or len(per_second_data) == 0:
                logger.warning("No per-second data generated")
                return None
            
            # Get unique phases for coloring
            phases = self.data['phase_id'].unique()
            phase_colors = plt.cm.Set1(range(len(phases)))
            phase_color_map = dict(zip(phases, phase_colors))
            
            # Plot per-second throughput over time with phase colors
            for phase in phases:
                phase_data = per_second_data[per_second_data['phase_id'] == phase]
                if len(phase_data) > 0:
                    plt.plot(phase_data['second'], phase_data['throughput_mbps'], 
                            marker='.', linewidth=1, markersize=2, 
                            color=phase_color_map[phase], label=f'Phase: {phase}', alpha=0.7)
            
            plt.title('Per-Second Throughput Timeline by Phase', fontsize=14)
            plt.xlabel('Time', fontsize=12)
            plt.ylabel('Throughput (Mbps)', fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.legend()
            plt.tight_layout()
            
            # Save plot
            output_file = os.path.join(self.output_dir, 'per_second_throughput_timeline.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Created per-second throughput timeline plot: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create per-second throughput plot: {e}")
            return None

    def _calculate_per_second_throughput_sweep_line(self):
        """Calculate per-second throughput using sweep line algorithm.
        
        The sweep line algorithm processes requests chronologically and maintains
        a sliding window of requests that contribute to each second's throughput.
        """
        if len(self.data) == 0:
            return None
        
        # Sort data by timestamp
        sorted_data = self.data.sort_values('ts').copy()
        
        # Create time range for sweep line
        start_time = sorted_data['ts'].min()
        end_time = sorted_data['ts'].max()
        
        # Generate all seconds in the range
        seconds = []
        current_time = start_time
        while current_time <= end_time:
            seconds.append(current_time)
            current_time += 1  # 1 second intervals
        
        # Initialize result data structure
        per_second_results = []
        
        # Sweep line algorithm: process each second
        for second_start in seconds:
            second_end = second_start + 1
            
            # Find all requests that overlap with this second
            # A request overlaps if it starts before the second ends and ends after the second starts
            overlapping_requests = sorted_data[
                (sorted_data['ts'] < second_end) & 
                (sorted_data['ts'] + sorted_data['latency_ms'] / 1000 >= second_start)
            ]
            
            if len(overlapping_requests) > 0:
                # Calculate bytes transferred in this second
                # For requests that span multiple seconds, we need to prorate
                total_bytes = 0
                phase_id = overlapping_requests['phase_id'].iloc[0]  # Assume consistent phase within second
                
                for _, request in overlapping_requests.iterrows():
                    request_start = request['ts']
                    request_end = request['ts'] + request['latency_ms'] / 1000
                    
                    # Calculate overlap duration with current second
                    overlap_start = max(request_start, second_start)
                    overlap_end = min(request_end, second_end)
                    overlap_duration = max(0, overlap_end - overlap_start)
                    
                    # Calculate total request duration
                    request_duration = request_end - request_start
                    
                    if request_duration > 0:
                        # Prorate bytes based on overlap duration
                        prorated_bytes = (request['bytes'] * overlap_duration) / request_duration
                        total_bytes += prorated_bytes
                
                # Calculate throughput in Mbps for this second
                throughput_mbps = (total_bytes * 8) / 1_000_000  # 1 second window
                
                per_second_results.append({
                    'second': pd.to_datetime(second_start, unit='s'),
                    'throughput_mbps': throughput_mbps,
                    'phase_id': phase_id,
                    'total_bytes': total_bytes,
                    'request_count': len(overlapping_requests)
                })
        
        if not per_second_results:
            return None
        
        # Convert to DataFrame
        result_df = pd.DataFrame(per_second_results)
        
        logger.info(f"Generated {len(result_df)} per-second throughput measurements")
        logger.info(f"Time range: {result_df['second'].min()} to {result_df['second'].max()}")
        
        return result_df
    
    def create_latency_histogram(self):
        """Create latency histogram plot."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for latency histogram")
            return None
        
        try:
            # Filter successful requests
            successful_data = self.data[self.data['http_status'] == 200]
            
            if len(successful_data) == 0:
                logger.warning("No successful requests for latency histogram")
                return None
            
            # Get unique concurrency levels
            concurrency_levels = sorted(successful_data['concurrency'].unique())
            
            # Create single plot
            plt.figure(figsize=(12, 8))
            
            # Histogram
            plt.hist(successful_data['latency_ms'], bins=50, alpha=0.7, edgecolor='black', color='skyblue')
            
            # Add concurrency info to title
            concurrency_str = ', '.join(map(str, concurrency_levels))
            plt.title(f'Overall Latency Distribution\nConcurrency Levels: {concurrency_str}', fontsize=14)
            plt.xlabel('Latency (ms)', fontsize=12)
            plt.ylabel('Frequency', fontsize=12)
            plt.grid(True, alpha=0.3)
            
            # Add statistics text box
            stats_text = f"""Statistics:
Total Requests: {len(successful_data):,}
Mean: {successful_data['latency_ms'].mean():.1f} ms
P50: {successful_data['latency_ms'].quantile(0.5):.1f} ms
P95: {successful_data['latency_ms'].quantile(0.95):.1f} ms
P99: {successful_data['latency_ms'].quantile(0.99):.1f} ms"""
            
            plt.text(0.02, 0.98, stats_text, transform=plt.gca().transAxes, 
                    fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle="round,pad=0.5", facecolor="lightblue", alpha=0.8))
            
            plt.tight_layout()
            
            # Save plot
            output_file = os.path.join(self.output_dir, 'latency_histogram.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Created latency histogram: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create latency histogram: {e}")
            return None
    
    def create_latency_boxplot(self):
        """Create latency box plot by concurrency."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for latency box plot")
            return None
        
        try:
            # Filter successful requests
            successful_data = self.data[self.data['http_status'] == 200]
            
            if len(successful_data) == 0:
                logger.warning("No successful requests for latency box plot")
                return None
            
            # Get unique concurrency levels
            concurrency_levels = sorted(successful_data['concurrency'].unique())
            
            # Create single plot
            plt.figure(figsize=(12, 8))
            
            if len(concurrency_levels) > 1:
                # Group data by concurrency for box plot
                latency_by_concurrency = [successful_data[successful_data['concurrency'] == c]['latency_ms'].values 
                                        for c in concurrency_levels]
                box_plot = plt.boxplot(latency_by_concurrency, labels=concurrency_levels, patch_artist=True)
                
                # Color boxes differently
                colors = plt.cm.Set3(range(len(concurrency_levels)))
                for patch, color in zip(box_plot['boxes'], colors):
                    patch.set_facecolor(color)
                    patch.set_alpha(0.7)
                
                plt.title('Latency Distribution by Concurrency Level', fontsize=14)
                plt.xlabel('Concurrency Level', fontsize=12)
                plt.ylabel('Latency (ms)', fontsize=12)
            else:
                # Single concurrency level - show simple box plot
                plt.boxplot(successful_data['latency_ms'])
                plt.title(f'Latency Distribution (Box Plot)\nConcurrency: {concurrency_levels[0]}', fontsize=14)
                plt.ylabel('Latency (ms)', fontsize=12)
            
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            # Save plot
            output_file = os.path.join(self.output_dir, 'latency_boxplot.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Created latency box plot: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create latency box plot: {e}")
            return None
    
    def create_latency_scatter(self):
        """Create latency vs concurrency scatter plot."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for latency scatter plot")
            return None
        
        try:
            # Filter successful requests
            successful_data = self.data[self.data['http_status'] == 200]
            
            if len(successful_data) == 0:
                logger.warning("No successful requests for latency scatter plot")
                return None
            
            # Get unique concurrency levels
            concurrency_levels = sorted(successful_data['concurrency'].unique())
            
            # Create single plot
            plt.figure(figsize=(12, 8))
            
            # Scatter plot: Latency vs Concurrency
            plt.scatter(successful_data['concurrency'], successful_data['latency_ms'], 
                       alpha=0.6, s=20, color='red')
            
            plt.title('Latency vs Concurrency', fontsize=14)
            plt.xlabel('Concurrency Level', fontsize=12)
            plt.ylabel('Latency (ms)', fontsize=12)
            plt.grid(True, alpha=0.3)
            
            # Add trend line if multiple concurrency levels
            if len(concurrency_levels) > 1:
                import numpy as np
                z = np.polyfit(successful_data['concurrency'], successful_data['latency_ms'], 1)
                p = np.poly1d(z)
                plt.plot(successful_data['concurrency'], p(successful_data['concurrency']), 
                        "b--", alpha=0.8, linewidth=2, label=f'Trend: y={z[0]:.1f}x+{z[1]:.1f}')
                plt.legend()
            
            plt.tight_layout()
            
            # Save plot
            output_file = os.path.join(self.output_dir, 'latency_scatter.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Created latency scatter plot: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create latency scatter plot: {e}")
            return None
    
    def create_latency_stats_table(self):
        """Create latency statistics table."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for latency stats table")
            return None
        
        try:
            # Filter successful requests
            successful_data = self.data[self.data['http_status'] == 200]
            
            if len(successful_data) == 0:
                logger.warning("No successful requests for latency stats table")
                return None
            
            # Get unique concurrency levels
            concurrency_levels = sorted(successful_data['concurrency'].unique())
            
            # Create statistics table
            table_data = []
            headers = ['Concurrency', 'Count', 'Mean (ms)', 'P50 (ms)', 'P95 (ms)', 'P99 (ms)', 'Min (ms)', 'Max (ms)']
            
            if len(concurrency_levels) > 1:
                for c in concurrency_levels:
                    c_data = successful_data[successful_data['concurrency'] == c]['latency_ms']
                    row = [
                        str(c),
                        str(len(c_data)),
                        f"{c_data.mean():.1f}",
                        f"{c_data.quantile(0.5):.1f}",
                        f"{c_data.quantile(0.95):.1f}",
                        f"{c_data.quantile(0.99):.1f}",
                        f"{c_data.min():.1f}",
                        f"{c_data.max():.1f}"
                    ]
                    table_data.append(row)
                
                # Add overall summary row
                overall_data = successful_data['latency_ms']
                summary_row = [
                    'ALL',
                    str(len(overall_data)),
                    f"{overall_data.mean():.1f}",
                    f"{overall_data.quantile(0.5):.1f}",
                    f"{overall_data.quantile(0.95):.1f}",
                    f"{overall_data.quantile(0.99):.1f}",
                    f"{overall_data.min():.1f}",
                    f"{overall_data.max():.1f}"
                ]
                table_data.append(summary_row)
            else:
                # Single concurrency level
                c_data = successful_data['latency_ms']
                row = [
                    str(concurrency_levels[0]),
                    str(len(c_data)),
                    f"{c_data.mean():.1f}",
                    f"{c_data.quantile(0.5):.1f}",
                    f"{c_data.quantile(0.95):.1f}",
                    f"{c_data.quantile(0.99):.1f}",
                    f"{c_data.min():.1f}",
                    f"{c_data.max():.1f}"
                ]
                table_data.append(row)
            
            # Create table file
            output_file = os.path.join(self.output_dir, 'latency_stats_table.txt')
            with open(output_file, 'w') as f:
                f.write("Latency Statistics by Concurrency Level\n")
                f.write("=" * 50 + "\n\n")
                
                # Write headers
                f.write(f"{'Concurrency':<12} {'Count':<8} {'Mean':<10} {'P50':<10} {'P95':<10} {'P99':<10} {'Min':<10} {'Max':<10}\n")
                f.write("-" * 90 + "\n")
                
                # Write data rows
                for row in table_data:
                    f.write(f"{row[0]:<12} {row[1]:<8} {row[2]:<10} {row[3]:<10} {row[4]:<10} {row[5]:<10} {row[6]:<10} {row[7]:<10}\n")
                
                f.write("\n")
                f.write(f"Total Requests: {len(successful_data):,}\n")
                f.write(f"Success Rate: {len(successful_data) / len(self.data) * 100:.2f}%\n")
                f.write(f"Concurrency Levels: {concurrency_levels}\n")
            
            logger.info(f"Created latency stats table: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create latency stats table: {e}")
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
        plots.append(self.create_per_second_throughput_timeline())  # New per-second plot
        plots.append(self.create_latency_histogram())
        plots.append(self.create_latency_boxplot())
        plots.append(self.create_latency_scatter())
        plots.append(self.create_latency_stats_table())
        plots.append(self.create_error_analysis())
        plots.append(self.create_summary_report())
        
        # Filter out None values
        plots = [p for p in plots if p is not None]
        
        logger.info(f"Created {len(plots)} plots and tables in {self.output_dir}")
        return plots

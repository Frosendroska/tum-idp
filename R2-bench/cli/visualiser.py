"""
Simple visualization for R2 benchmark results.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
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
        """Create comprehensive latency histogram plot with multiple views."""
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
            
            # Create subplot layout
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('Comprehensive Latency Analysis', fontsize=16, fontweight='bold')
            
            # 1. Overall histogram
            ax1 = axes[0, 0]
            ax1.hist(successful_data['latency_ms'], bins=50, alpha=0.7, edgecolor='black', color='skyblue')
            ax1.set_title('Overall Latency Distribution', fontsize=12)
            ax1.set_xlabel('Latency (ms)')
            ax1.set_ylabel('Frequency')
            ax1.grid(True, alpha=0.3)
            
            # 2. Log-scale histogram for better visibility
            ax2 = axes[0, 1]
            ax2.hist(successful_data['latency_ms'], bins=50, alpha=0.7, edgecolor='black', color='lightcoral')
            ax2.set_yscale('log')
            ax2.set_title('Latency Distribution (Log Scale)', fontsize=12)
            ax2.set_xlabel('Latency (ms)')
            ax2.set_ylabel('Frequency (log scale)')
            ax2.grid(True, alpha=0.3)
            
            # 3. CDF plot
            ax3 = axes[1, 0]
            sorted_latencies = np.sort(successful_data['latency_ms'])
            y = np.arange(1, len(sorted_latencies) + 1) / len(sorted_latencies)
            ax3.plot(sorted_latencies, y, linewidth=2, color='green')
            ax3.set_title('Cumulative Distribution Function', fontsize=12)
            ax3.set_xlabel('Latency (ms)')
            ax3.set_ylabel('Cumulative Probability')
            ax3.grid(True, alpha=0.3)
            
            # 4. Latency by concurrency (if multiple levels)
            ax4 = axes[1, 1]
            if len(concurrency_levels) > 1:
                for i, concurrency in enumerate(concurrency_levels):
                    c_data = successful_data[successful_data['concurrency'] == concurrency]['latency_ms']
                    ax4.hist(c_data, bins=20, alpha=0.6, label=f'Concurrency {concurrency}', 
                            color=plt.cm.Set1(i))
                ax4.set_title('Latency Distribution by Concurrency', fontsize=12)
                ax4.legend()
            else:
                # Single concurrency - show density plot
                ax4.hist(successful_data['latency_ms'], bins=50, alpha=0.7, density=True, 
                        edgecolor='black', color='purple')
                ax4.set_title('Latency Density Distribution', fontsize=12)
            ax4.set_xlabel('Latency (ms)')
            ax4.set_ylabel('Density' if len(concurrency_levels) == 1 else 'Frequency')
            ax4.grid(True, alpha=0.3)
            
            # Add statistics text box
            stats_text = f"""Statistics:
Total Requests: {len(successful_data):,}
Mean: {successful_data['latency_ms'].mean():.1f} ms
P50: {successful_data['latency_ms'].quantile(0.5):.1f} ms
P95: {successful_data['latency_ms'].quantile(0.95):.1f} ms
P99: {successful_data['latency_ms'].quantile(0.99):.1f} ms
Std: {successful_data['latency_ms'].std():.1f} ms"""
            
            fig.text(0.02, 0.02, stats_text, fontsize=9, verticalalignment='bottom',
                    bbox=dict(boxstyle="round,pad=0.5", facecolor="lightblue", alpha=0.8))
            
            plt.tight_layout()
            
            # Save plot
            output_file = os.path.join(self.output_dir, 'latency_histogram.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Created enhanced latency histogram: {output_file}")
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
    
    def create_throughput_vs_concurrency(self):
        """Create throughput vs concurrency analysis plot."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for throughput vs concurrency plot")
            return None
        
        try:
            # Filter successful requests
            successful_data = self.data[self.data['http_status'] == 200]
            
            if len(successful_data) == 0:
                logger.warning("No successful requests for throughput vs concurrency plot")
                return None
            
            # Group by concurrency and calculate metrics
            concurrency_stats = successful_data.groupby('concurrency').agg({
                'bytes': 'sum',
                'latency_ms': ['mean', 'std', 'count'],
                'ts': ['min', 'max']
            }).reset_index()
            
            # Flatten column names
            concurrency_stats.columns = ['concurrency', 'total_bytes', 'avg_latency', 'latency_std', 'request_count', 'start_time', 'end_time']
            
            # Calculate throughput for each concurrency level
            concurrency_stats['duration_seconds'] = concurrency_stats['end_time'] - concurrency_stats['start_time']
            concurrency_stats['throughput_mbps'] = (concurrency_stats['total_bytes'] * 8) / (concurrency_stats['duration_seconds'] * 1_000_000)
            concurrency_stats['requests_per_second'] = concurrency_stats['request_count'] / concurrency_stats['duration_seconds']
            
            # Create subplot layout
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('Throughput vs Concurrency Analysis', fontsize=16, fontweight='bold')
            
            # 1. Throughput vs Concurrency
            ax1 = axes[0, 0]
            ax1.plot(concurrency_stats['concurrency'], concurrency_stats['throughput_mbps'], 
                    marker='o', linewidth=2, markersize=8, color='blue')
            ax1.set_title('Throughput vs Concurrency', fontsize=12)
            ax1.set_xlabel('Concurrency Level')
            ax1.set_ylabel('Throughput (Mbps)')
            ax1.grid(True, alpha=0.3)
            
            # 2. Requests per Second vs Concurrency
            ax2 = axes[0, 1]
            ax2.plot(concurrency_stats['concurrency'], concurrency_stats['requests_per_second'], 
                    marker='s', linewidth=2, markersize=8, color='green')
            ax2.set_title('Request Rate vs Concurrency', fontsize=12)
            ax2.set_xlabel('Concurrency Level')
            ax2.set_ylabel('Requests per Second')
            ax2.grid(True, alpha=0.3)
            
            # 3. Latency vs Concurrency
            ax3 = axes[1, 0]
            ax3.plot(concurrency_stats['concurrency'], concurrency_stats['avg_latency'], 
                    marker='^', linewidth=2, markersize=8, color='red')
            ax3.fill_between(concurrency_stats['concurrency'], 
                           concurrency_stats['avg_latency'] - concurrency_stats['latency_std'],
                           concurrency_stats['avg_latency'] + concurrency_stats['latency_std'],
                           alpha=0.3, color='red')
            ax3.set_title('Average Latency vs Concurrency', fontsize=12)
            ax3.set_xlabel('Concurrency Level')
            ax3.set_ylabel('Average Latency (ms)')
            ax3.grid(True, alpha=0.3)
            
            # 4. Efficiency (throughput per connection)
            ax4 = axes[1, 1]
            concurrency_stats['efficiency'] = concurrency_stats['throughput_mbps'] / concurrency_stats['concurrency']
            ax4.plot(concurrency_stats['concurrency'], concurrency_stats['efficiency'], 
                    marker='d', linewidth=2, markersize=8, color='purple')
            ax4.set_title('Efficiency (Throughput per Connection)', fontsize=12)
            ax4.set_xlabel('Concurrency Level')
            ax4.set_ylabel('Efficiency (Mbps per Connection)')
            ax4.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Save plot
            output_file = os.path.join(self.output_dir, 'throughput_vs_concurrency.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Created throughput vs concurrency plot: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create throughput vs concurrency plot: {e}")
            return None
    
    def create_latency_over_time(self):
        """Create latency over time plot."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for latency over time plot")
            return None
        
        try:
            # Filter successful requests
            successful_data = self.data[self.data['http_status'] == 200]
            
            if len(successful_data) == 0:
                logger.warning("No successful requests for latency over time plot")
                return None
            
            # Convert timestamp to datetime
            successful_data = successful_data.copy()
            successful_data['datetime'] = pd.to_datetime(successful_data['ts'], unit='s')
            
            # Create subplot layout
            fig, axes = plt.subplots(2, 1, figsize=(15, 10))
            fig.suptitle('Latency Analysis Over Time', fontsize=16, fontweight='bold')
            
            # 1. Latency scatter plot over time
            ax1 = axes[0]
            scatter = ax1.scatter(successful_data['datetime'], successful_data['latency_ms'], 
                                c=successful_data['concurrency'], cmap='viridis', alpha=0.6, s=20)
            ax1.set_title('Latency Over Time (colored by concurrency)', fontsize=12)
            ax1.set_xlabel('Time')
            ax1.set_ylabel('Latency (ms)')
            ax1.grid(True, alpha=0.3)
            plt.colorbar(scatter, ax=ax1, label='Concurrency Level')
            
            # 2. Rolling average latency
            ax2 = axes[1]
            # Calculate rolling average with 30-second windows
            successful_data_sorted = successful_data.sort_values('ts')
            successful_data_sorted['rolling_avg_latency'] = successful_data_sorted['latency_ms'].rolling(window=10, min_periods=1).mean()
            
            ax2.plot(successful_data_sorted['datetime'], successful_data_sorted['rolling_avg_latency'], 
                    linewidth=2, color='red', alpha=0.8)
            ax2.set_title('Rolling Average Latency (10-request window)', fontsize=12)
            ax2.set_xlabel('Time')
            ax2.set_ylabel('Rolling Average Latency (ms)')
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Save plot
            output_file = os.path.join(self.output_dir, 'latency_over_time.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Created latency over time plot: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create latency over time plot: {e}")
            return None
    
    def create_violin_plot(self):
        """Create violin plot for latency distribution by concurrency."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for violin plot")
            return None
        
        try:
            # Filter successful requests
            successful_data = self.data[self.data['http_status'] == 200]
            
            if len(successful_data) == 0:
                logger.warning("No successful requests for violin plot")
                return None
            
            # Get unique concurrency levels
            concurrency_levels = sorted(successful_data['concurrency'].unique())
            
            if len(concurrency_levels) < 2:
                logger.warning("Need at least 2 concurrency levels for violin plot")
                return None
            
            plt.figure(figsize=(12, 8))
            
            # Prepare data for violin plot
            violin_data = []
            labels = []
            for concurrency in concurrency_levels:
                c_data = successful_data[successful_data['concurrency'] == concurrency]['latency_ms']
                violin_data.append(c_data.values)
                labels.append(f'Concurrency {concurrency}')
            
            # Create violin plot
            parts = plt.violinplot(violin_data, positions=range(len(concurrency_levels)), 
                                 showmeans=True, showmedians=True, showextrema=True)
            
            # Customize violin plot
            colors = plt.cm.Set2(range(len(concurrency_levels)))
            for i, pc in enumerate(parts['bodies']):
                pc.set_facecolor(colors[i])
                pc.set_alpha(0.7)
            
            plt.title('Latency Distribution by Concurrency Level (Violin Plot)', fontsize=14)
            plt.xlabel('Concurrency Level', fontsize=12)
            plt.ylabel('Latency (ms)', fontsize=12)
            plt.xticks(range(len(concurrency_levels)), labels)
            plt.grid(True, alpha=0.3)
            
            # Add statistics text
            stats_text = f"""Statistics:
Total Concurrency Levels: {len(concurrency_levels)}
Total Requests: {len(successful_data):,}
Mean Latency: {successful_data['latency_ms'].mean():.1f} ms"""
            
            plt.text(0.02, 0.98, stats_text, transform=plt.gca().transAxes, 
                    fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgreen", alpha=0.8))
            
            plt.tight_layout()
            
            # Save plot
            output_file = os.path.join(self.output_dir, 'latency_violin_plot.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Created violin plot: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create violin plot: {e}")
            return None
    
    def create_performance_dashboard(self):
        """Create a comprehensive performance dashboard."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for performance dashboard")
            return None
        
        try:
            # Filter successful requests
            successful_data = self.data[self.data['http_status'] == 200]
            
            if len(successful_data) == 0:
                logger.warning("No successful requests for performance dashboard")
                return None
            
            # Create large dashboard
            fig = plt.figure(figsize=(20, 16))
            gs = fig.add_gridspec(4, 4, hspace=0.3, wspace=0.3)
            fig.suptitle('R2 Benchmark Performance Dashboard', fontsize=20, fontweight='bold')
            
            # 1. Throughput timeline (top row, spans 2 columns)
            ax1 = fig.add_subplot(gs[0, :2])
            self.data['datetime'] = pd.to_datetime(self.data['ts'], unit='s')
            self.data['time_window'] = self.data['datetime'].dt.floor('30s')
            throughput_data = self.data.groupby('time_window').agg({
                'bytes': 'sum',
                'phase_id': 'first'
            }).reset_index()
            throughput_data['throughput_mbps'] = (throughput_data['bytes'] * 8) / (30 * 1_000_000)
            
            phases = self.data['phase_id'].unique()
            phase_colors = plt.cm.Set1(range(len(phases)))
            phase_color_map = dict(zip(phases, phase_colors))
            
            for phase in phases:
                phase_data = throughput_data[throughput_data['phase_id'] == phase]
                if len(phase_data) > 0:
                    ax1.plot(phase_data['time_window'], phase_data['throughput_mbps'], 
                            marker='o', linewidth=2, markersize=4, 
                            color=phase_color_map[phase], label=f'Phase: {phase}')
            
            ax1.set_title('Throughput Timeline', fontsize=14)
            ax1.set_ylabel('Throughput (Mbps)')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            
            # 2. Latency distribution (top right)
            ax2 = fig.add_subplot(gs[0, 2:])
            ax2.hist(successful_data['latency_ms'], bins=30, alpha=0.7, edgecolor='black', color='skyblue')
            ax2.set_title('Latency Distribution', fontsize=14)
            ax2.set_xlabel('Latency (ms)')
            ax2.set_ylabel('Frequency')
            ax2.grid(True, alpha=0.3)
            
            # 3. Concurrency vs Throughput (second row, left)
            ax3 = fig.add_subplot(gs[1, :2])
            concurrency_stats = successful_data.groupby('concurrency').agg({
                'bytes': 'sum',
                'ts': ['min', 'max']
            }).reset_index()
            concurrency_stats.columns = ['concurrency', 'total_bytes', 'start_time', 'end_time']
            concurrency_stats['duration_seconds'] = concurrency_stats['end_time'] - concurrency_stats['start_time']
            concurrency_stats['throughput_mbps'] = (concurrency_stats['total_bytes'] * 8) / (concurrency_stats['duration_seconds'] * 1_000_000)
            
            ax3.plot(concurrency_stats['concurrency'], concurrency_stats['throughput_mbps'], 
                    marker='o', linewidth=2, markersize=8, color='blue')
            ax3.set_title('Throughput vs Concurrency', fontsize=14)
            ax3.set_xlabel('Concurrency Level')
            ax3.set_ylabel('Throughput (Mbps)')
            ax3.grid(True, alpha=0.3)
            
            # 4. Error rate (second row, right)
            ax4 = fig.add_subplot(gs[1, 2:])
            total_requests = len(self.data)
            successful_requests = len(successful_data)
            error_requests = total_requests - successful_requests
            error_rate = error_requests / total_requests if total_requests > 0 else 0
            
            ax4.bar(['Successful', 'Failed'], [successful_requests, error_requests], 
                   color=['green', 'red'], alpha=0.7)
            ax4.set_title(f'Request Success Rate: {successful_requests/total_requests*100:.1f}%', fontsize=14)
            ax4.set_ylabel('Number of Requests')
            ax4.grid(True, alpha=0.3)
            
            # 5. Latency percentiles (third row, left)
            ax5 = fig.add_subplot(gs[2, :2])
            percentiles = [50, 90, 95, 99]
            latency_percentiles = [successful_data['latency_ms'].quantile(p/100) for p in percentiles]
            ax5.bar([f'P{p}' for p in percentiles], latency_percentiles, 
                   color=['blue', 'orange', 'red', 'darkred'], alpha=0.7)
            ax5.set_title('Latency Percentiles', fontsize=14)
            ax5.set_ylabel('Latency (ms)')
            ax5.grid(True, alpha=0.3)
            
            # 6. Phase summary (third row, right)
            ax6 = fig.add_subplot(gs[2, 2:])
            phase_summary = self.data.groupby('phase_id').agg({
                'bytes': 'sum',
                'latency_ms': 'mean',
                'ts': ['min', 'max']
            }).reset_index()
            phase_summary.columns = ['phase_id', 'total_bytes', 'avg_latency', 'start_time', 'end_time']
            phase_summary['duration'] = phase_summary['end_time'] - phase_summary['start_time']
            phase_summary['throughput_mbps'] = (phase_summary['total_bytes'] * 8) / (phase_summary['duration'] * 1_000_000)
            
            ax6.bar(phase_summary['phase_id'], phase_summary['throughput_mbps'], 
                   color=plt.cm.Set3(range(len(phase_summary))), alpha=0.7)
            ax6.set_title('Throughput by Phase', fontsize=14)
            ax6.set_ylabel('Throughput (Mbps)')
            ax6.tick_params(axis='x', rotation=45)
            ax6.grid(True, alpha=0.3)
            
            # 7. Key metrics summary (bottom row, full width)
            ax7 = fig.add_subplot(gs[3, :])
            ax7.axis('off')
            
            # Calculate key metrics
            total_duration = self.data['ts'].max() - self.data['ts'].min()
            total_bytes = successful_data['bytes'].sum()
            avg_throughput = (total_bytes * 8) / (total_duration * 1_000_000)
            avg_latency = successful_data['latency_ms'].mean()
            p95_latency = successful_data['latency_ms'].quantile(0.95)
            p99_latency = successful_data['latency_ms'].quantile(0.99)
            
            metrics_text = f"""
            KEY PERFORMANCE METRICS
            ========================
            Total Duration: {total_duration/3600:.2f} hours
            Total Data Transferred: {total_bytes/(1024**3):.2f} GB
            Average Throughput: {avg_throughput:.1f} Mbps
            Average Latency: {avg_latency:.1f} ms
            P95 Latency: {p95_latency:.1f} ms
            P99 Latency: {p99_latency:.1f} ms
            Success Rate: {successful_requests/total_requests*100:.2f}%
            Concurrency Levels: {sorted(self.data['concurrency'].unique())}
            """
            
            ax7.text(0.1, 0.5, metrics_text, fontsize=12, verticalalignment='center',
                    bbox=dict(boxstyle="round,pad=1", facecolor="lightblue", alpha=0.8))
            
            # Save plot
            output_file = os.path.join(self.output_dir, 'performance_dashboard.png')
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Created performance dashboard: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create performance dashboard: {e}")
            return None

    def create_all_plots(self):
        """Create all available plots."""
        plots = []
        
        plots.append(self.create_throughput_timeline())
        plots.append(self.create_per_second_throughput_timeline())
        plots.append(self.create_latency_histogram())
        plots.append(self.create_latency_boxplot())
        plots.append(self.create_latency_scatter())
        plots.append(self.create_throughput_vs_concurrency())
        plots.append(self.create_latency_over_time())
        plots.append(self.create_violin_plot())
        plots.append(self.create_performance_dashboard())
        plots.append(self.create_latency_stats_table())
        plots.append(self.create_error_analysis())
        plots.append(self.create_summary_report())
        
        # Filter out None values
        plots = [p for p in plots if p is not None]
        
        logger.info(f"Created {len(plots)} plots and tables in {self.output_dir}")
        return plots

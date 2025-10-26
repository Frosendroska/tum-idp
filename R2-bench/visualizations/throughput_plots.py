"""
Throughput visualization plots.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import logging
import os

from .base import BasePlotter

logger = logging.getLogger(__name__)


class ThroughputPlotter(BasePlotter):
    """Plotter for throughput-related visualizations."""
    
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
            self.data['time_window'] = self.data['datetime'].dt.floor('30s')
            throughput_data = self.data.groupby('time_window').agg({
                'bytes': 'sum',
                'latency_ms': 'mean',
                'phase_id': 'first'
            }).reset_index()
            
            # Calculate throughput in Mbps
            throughput_data['throughput_mbps'] = (throughput_data['bytes'] * 8) / (30 * 1_000_000)
            
            # Get unique phases for coloring
            phase_color_map = self.get_phase_colors()
            
            # Plot throughput over time with phase colors
            phases = self.get_unique_phases()
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
            
            # Use sweep line algorithm for per-second throughput calculation
            per_second_data = self._calculate_per_second_throughput_sweep_line()
            
            if per_second_data is None or len(per_second_data) == 0:
                logger.warning("No per-second data generated")
                return None
            
            # Get unique phases for coloring
            phase_color_map = self.get_phase_colors()
            
            # Plot per-second throughput over time with phase colors
            phases = self.get_unique_phases()
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
            current_time += 1
        
        # Initialize result data structure
        per_second_results = []
        
        # Sweep line algorithm: process each second
        for second_start in seconds:
            second_end = second_start + 1
            
            # Find all requests that overlap with this second
            overlapping_requests = sorted_data[
                (sorted_data['ts'] < second_end) & 
                (sorted_data['ts'] + sorted_data['latency_ms'] / 1000 >= second_start)
            ]
            
            if len(overlapping_requests) > 0:
                # Calculate bytes transferred in this second
                total_bytes = 0
                phase_id = overlapping_requests['phase_id'].iloc[0]
                
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
                throughput_mbps = (total_bytes * 8) / 1_000_000
                
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
    
    def create_throughput_vs_concurrency(self):
        """Create throughput vs concurrency analysis plot."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for throughput vs concurrency plot")
            return None
        
        try:
            successful_data = self.filter_successful_requests()
            
            if successful_data is None or len(successful_data) == 0:
                logger.warning("No successful requests for throughput vs concurrency plot")
                return None
            
            # Group by concurrency and calculate metrics
            concurrency_stats = successful_data.groupby('concurrency').agg({
                'bytes': 'sum',
                'latency_ms': ['mean', 'std', 'count'],
                'ts': ['min', 'max']
            }).reset_index()
            
            # Flatten column names
            concurrency_stats.columns = ['concurrency', 'total_bytes', 'avg_latency', 'latency_std', 
                                        'request_count', 'start_time', 'end_time']
            
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
    
    def create_throughput_stats_table(self):
        """Create throughput statistics table by phase/step."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for throughput stats table")
            return None
        
        try:
            successful_data = self.filter_successful_requests()
            
            if successful_data is None or len(successful_data) == 0:
                logger.warning("No successful requests for throughput stats table")
                return None
            
            # Group by phase and calculate metrics
            phase_stats = successful_data.groupby('phase_id').agg({
                'bytes': 'sum',
                'ts': ['min', 'max', 'count'],
                'latency_ms': 'mean',
                'concurrency': 'mean'
            }).reset_index()
            
            # Flatten column names
            phase_stats.columns = ['phase_id', 'total_bytes', 'start_time', 'end_time', 
                                  'request_count', 'avg_latency', 'avg_concurrency']
            
            # Calculate throughput for each phase
            phase_stats['duration_seconds'] = phase_stats['end_time'] - phase_stats['start_time']
            phase_stats['throughput_mbps'] = (phase_stats['total_bytes'] * 8) / (phase_stats['duration_seconds'] * 1_000_000)
            phase_stats['requests_per_second'] = phase_stats['request_count'] / phase_stats['duration_seconds']
            phase_stats['total_gb'] = phase_stats['total_bytes'] / (1024**3)
            
            # Create table data
            table_data = []
            headers = ['Phase', 'Duration (s)', 'Requests', 'Total Data (GB)', 
                      'Throughput (Mbps)', 'Req/s', 'Avg Latency (ms)', 'Avg Concurrency']
            
            # Define sort key function to ensure warmup comes first, then ramp steps in order, then ALL
            def phase_sort_key(phase_id):
                if phase_id == 'warmup':
                    return (0, 0)  # warmup comes first
                elif phase_id == 'ALL':
                    return (2, 999)  # ALL comes last
                elif phase_id.startswith('ramp_'):
                    try:
                        num = int(phase_id.split('_')[1])
                        return (1, num)  # ramp steps after warmup
                    except (IndexError, ValueError):
                        return (1, 999)  # invalid ramp ID
                else:
                    return (3, 999)  # everything else
            
            # Sort the phase_stats DataFrame by phase_id using the custom sort key
            phase_stats['sort_key'] = phase_stats['phase_id'].apply(phase_sort_key)
            phase_stats = phase_stats.sort_values('sort_key')
            
            for _, row in phase_stats.iterrows():
                table_row = [
                    str(row['phase_id']),
                    f"{row['duration_seconds']:.1f}",
                    str(int(row['request_count'])),
                    f"{row['total_gb']:.3f}",
                    f"{row['throughput_mbps']:.2f}",
                    f"{row['requests_per_second']:.2f}",
                    f"{row['avg_latency']:.1f}",
                    f"{row['avg_concurrency']:.0f}"
                ]
                table_data.append(table_row)
            
            # Add overall summary row
            total_bytes = successful_data['bytes'].sum()
            total_duration = successful_data['ts'].max() - successful_data['ts'].min()
            total_requests = len(successful_data)
            overall_throughput = (total_bytes * 8) / (total_duration * 1_000_000) if total_duration > 0 else 0
            overall_rps = total_requests / total_duration if total_duration > 0 else 0
            overall_latency = successful_data['latency_ms'].mean()
            overall_concurrency = successful_data['concurrency'].mean()
            
            summary_row = [
                'ALL',
                f"{total_duration:.1f}",
                str(total_requests),
                f"{total_bytes / (1024**3):.3f}",
                f"{overall_throughput:.2f}",
                f"{overall_rps:.2f}",
                f"{overall_latency:.1f}",
                f"{overall_concurrency:.0f}"
            ]
            table_data.append(summary_row)
            
            # Create table file
            output_file = os.path.join(self.output_dir, 'throughput_stats_table.txt')
            with open(output_file, 'w') as f:
                f.write("Throughput Statistics by Phase/Step\n")
                f.write("=" * 100 + "\n\n")
                
                # Write headers
                f.write(f"{'Phase':<12} {'Duration':<12} {'Requests':<12} {'Data (GB)':<12} "
                       f"{'Throughput':<15} {'Req/s':<10} {'Latency (ms)':<15} {'Concurrency':<12}\n")
                f.write("-" * 100 + "\n")
                
                # Write data rows
                for row in table_data:
                    f.write(f"{row[0]:<12} {row[1]:<12} {row[2]:<12} {row[3]:<12} "
                           f"{row[4]:<15} {row[5]:<10} {row[6]:<15} {row[7]:<12}\n")
                
                f.write("\n")
                f.write(f"Total Requests: {len(successful_data):,}\n")
                f.write(f"Success Rate: {len(successful_data) / len(self.data) * 100:.2f}%\n")
            
            logger.info(f"Created throughput stats table: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to create throughput stats table: {e}")
            return None


"""
Throughput visualization plots.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import logging
import os

from .base import BasePlotter
from .throughput_utils import (
    prorate_bytes_to_time_windows,
    calculate_phase_throughput_with_prorating,
    get_phase_boundaries
)

logger = logging.getLogger(__name__)


class ThroughputPlotter(BasePlotter):
    """Plotter for throughput-related visualizations."""
    
    def create_throughput_timeline(self):
        """Create throughput timeline plot with phase information using prorated 30-second windows."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for throughput plot")
            return None
        
        try:
            plt.figure(figsize=(15, 8))
            
            # Use start_ts/end_ts for time range
            start_time = self.data['start_ts'].min()
            end_time = self.data['end_ts'].max()
            
            # Generate 30-second windows
            window_size = 30.0
            window_start_times = []
            current_time = start_time
            while current_time <= end_time:
                window_start_times.append(current_time)
                current_time += window_size
            
            # Use prorating utility for 30-second windows
            throughput_data = prorate_bytes_to_time_windows(
                self.data,
                window_start_times,
                window_size_seconds=window_size,
                start_col='start_ts',
                end_col='end_ts'
            )
            
            if throughput_data is None or len(throughput_data) == 0:
                logger.warning("No throughput data generated")
                return None
            
            # Get unique phases for coloring
            phase_color_map = self.get_phase_colors()
            
            # Plot throughput over time with phase colors
            phases = self.get_unique_phases()
            for phase in phases:
                phase_data = throughput_data[throughput_data['phase_id'] == phase]
                if len(phase_data) > 0:
                    plt.plot(phase_data['window_start'], phase_data['throughput_mbps'], 
                            marker='o', linewidth=2, markersize=4, 
                            color=phase_color_map[phase], label=f'Phase: {phase}')
            
            plt.title('Throughput Timeline by Phase (30s windows, prorated)', fontsize=14)
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
        """Calculate per-second throughput using sweep line algorithm with start_ts/end_ts.
        
        The sweep line algorithm processes requests chronologically and maintains
        a sliding window of requests that contribute to each second's throughput.
        Uses start_ts/end_ts for accurate timing and prorates bytes across seconds.
        """
        if len(self.data) == 0:
            return None
        
        # Use start_ts/end_ts for time range
        start_time = self.data['start_ts'].min()
        end_time = self.data['end_ts'].max()
        
        # Generate all seconds in the range
        seconds = []
        current_time = int(start_time)
        while current_time <= int(end_time) + 1:
            seconds.append(float(current_time))
            current_time += 1
        
        # Use shared prorating utility
        per_second_data = prorate_bytes_to_time_windows(
            self.data,
            seconds,
            window_size_seconds=1.0,
            start_col='start_ts',
            end_col='end_ts'
        )
        
        if per_second_data is None or len(per_second_data) == 0:
            return None
        
        # Rename column for compatibility
        per_second_data = per_second_data.rename(columns={'window_start': 'second'})
        
        logger.info(f"Generated {len(per_second_data)} per-second throughput measurements")
        logger.info(f"Time range: {per_second_data['second'].min()} to {per_second_data['second'].max()}")
        
        return per_second_data
    
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
            
            # Group by concurrency and calculate metrics using start_ts/end_ts
            concurrency_stats = successful_data.groupby('concurrency').agg({
                'bytes': 'sum',
                'latency_ms': ['mean', 'std', 'count'],
                'start_ts': 'min',
                'end_ts': 'max'
            }).reset_index()
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
            
            # Calculate throughput for each phase using prorating utility
            # First, get phase boundaries from all data
            phase_boundaries = get_phase_boundaries(successful_data)
            
            phase_stats_list = []
            for phase_id in successful_data['phase_id'].unique():
                # Use the new prorating function that considers ALL requests overlapping with the phase
                phase_result = calculate_phase_throughput_with_prorating(
                    successful_data,  # Pass all data, not just phase_data
                    phase_id=phase_id,
                    phase_boundaries=phase_boundaries
                )
                
                # Get additional stats from requests that started in this phase
                phase_data = successful_data[successful_data['phase_id'] == phase_id]
                phase_result['phase_id'] = phase_id
                phase_result['avg_latency'] = phase_data['latency_ms'].mean() if len(phase_data) > 0 else 0
                phase_result['avg_concurrency'] = phase_data['concurrency'].mean() if len(phase_data) > 0 else 0
                phase_result['requests_per_second'] = phase_result['request_count'] / phase_result['duration_seconds'] if phase_result['duration_seconds'] > 0 else 0
                phase_result['total_gb'] = phase_result['total_bytes'] / (1024**3)
                
                phase_stats_list.append(phase_result)
            
            phase_stats = pd.DataFrame(phase_stats_list)
            
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
            
            # Add overall summary row using start_ts/end_ts
            total_bytes = successful_data['bytes'].sum()
            total_duration = successful_data['end_ts'].max() - successful_data['start_ts'].min()
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


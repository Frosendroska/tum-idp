"""
Dashboard and summary report visualizations.
"""

import pandas as pd
import matplotlib.pyplot as plt
import logging
import os

from .base import BasePlotter

logger = logging.getLogger(__name__)


class DashboardPlotter(BasePlotter):
    """Plotter for dashboard and summary visualizations."""
    
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
            successful_data = self.filter_successful_requests()
            if successful_data is not None and len(successful_data) > 0:
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

Data Source: {self.data_source}
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
    
    def create_performance_dashboard(self):
        """Create a comprehensive performance dashboard."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for performance dashboard")
            return None
        
        try:
            successful_data = self.filter_successful_requests()
            
            if successful_data is None or len(successful_data) == 0:
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
            
            phase_color_map = self.get_phase_colors()
            phases = self.get_unique_phases()
            
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


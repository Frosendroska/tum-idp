"""
Latency visualization plots.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import logging
import os

from .base import BasePlotter

logger = logging.getLogger(__name__)


class LatencyPlotter(BasePlotter):
    """Plotter for latency-related visualizations."""
    
    def create_latency_histogram(self):
        """Create comprehensive latency histogram plot with multiple views."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for latency histogram")
            return None
        
        try:
            successful_data = self.filter_successful_requests()
            
            if successful_data is None or len(successful_data) == 0:
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
            successful_data = self.filter_successful_requests()
            
            if successful_data is None or len(successful_data) == 0:
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
            successful_data = self.filter_successful_requests()
            
            if successful_data is None or len(successful_data) == 0:
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
            successful_data = self.filter_successful_requests()
            
            if successful_data is None or len(successful_data) == 0:
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
    
    def create_latency_over_time(self):
        """Create latency over time plot."""
        if self.data is None or len(self.data) == 0:
            logger.warning("No data available for latency over time plot")
            return None
        
        try:
            successful_data = self.filter_successful_requests()
            
            if successful_data is None or len(successful_data) == 0:
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
            successful_data = self.filter_successful_requests()
            
            if successful_data is None or len(successful_data) == 0:
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


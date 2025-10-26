# Visualizations Module

This directory contains visualization logic for R2 benchmark results.

## Directory Structure

```
R2-bench/
├── plots/                   # Output directory for visualization results
├── visualizations/          # Visualization module
    ├── __init__.py          # Module exports
    ├── base.py              # Base classes and utilities
    ├── throughput_plots.py  # Throughput-related visualizations
    ├── latency_plots.py     # Latency-related visualizations
    ├── dashboard.py         # Dashboard and summary reports
    └── README.md            # This file
```

## Architecture

The visualization system has been refactored for better modularity and maintainability:

### Base Classes (`base.py`)

- `BasePlotter`: Base class providing common functionality for all plotters
  - `filter_successful_requests()`: Filter data to only successful HTTP requests
  - `get_unique_phases()`: Get unique phase IDs from data
  - `get_phase_colors()`: Generate color map for phases

### Plot Modules

#### 1. Throughput Plots (`throughput_plots.py`)
- `ThroughputPlotter`: Handles all throughput-related visualizations
  - `create_throughput_timeline()`: Timeline of throughput over time
  - `create_per_second_throughput_timeline()`: Per-second throughput using sweep line algorithm
  - `create_throughput_vs_concurrency()`: Throughput analysis by concurrency level
  - `create_throughput_stats_table()`: Text table with throughput statistics per phase/step

#### 2. Latency Plots (`latency_plots.py`)
- `LatencyPlotter`: Handles all latency-related visualizations
  - `create_latency_histogram()`: Comprehensive latency distribution
  - `create_latency_boxplot()`: Box plot by concurrency level
  - `create_latency_scatter()`: Latency vs concurrency scatter plot
  - `create_latency_stats_table()`: Statistics table with percentiles
  - `create_latency_over_time()`: Latency over time analysis
  - `create_violin_plot()`: Violin plot for distribution comparison
  - `create_error_analysis()`: HTTP status code distribution

#### 3. Dashboard (`dashboard.py`)
- `DashboardPlotter`: Creates comprehensive dashboards and summaries
  - `create_performance_dashboard()`: Multi-panel performance dashboard
  - `create_summary_report()`: Text summary report with key metrics

## Usage

The main `BenchmarkVisualizer` class in `cli/visualiser.py` orchestrates these modular plotters:

```python
from cli.visualiser import BenchmarkVisualizer

# Initialize visualizer
vis = BenchmarkVisualizer('results/benchmark.parquet', 'plots')

# Create all plots
vis.create_all_plots()

# Or create specific plots
vis.create_throughput_timeline()
vis.create_latency_histogram()
vis.create_performance_dashboard()
```

## Benefits of Modular Design

1. **Separation of Concerns**: Each plot module focuses on a specific type of visualization
2. **Maintainability**: Easier to locate and update specific visualization code
3. **Extensibility**: New plot types can be added by creating new modules or classes
4. **Testability**: Each module can be tested independently
5. **Readability**: Smaller, focused files are easier to understand

## Adding New Plots

To add a new visualization:

1. Determine which module it belongs to (or create a new one)
2. Add a method to the appropriate Plotter class
3. The method should:
   - Check for data availability
   - Create the plot using matplotlib
   - Save to `self.output_dir`
   - Return the output file path
4. Add a delegating method in `BenchmarkVisualizer` if needed

## Notes

- All plot methods return the output file path on success, or `None` on failure
- Plot data is passed to plotter instances during initialization
- Each plotter has access to the shared data and output directory


# R2 Benchmark Implementation Guide

This document provides a complete guide to implementing and running the R2 Large-Chunk GET Microbenchmark as specified in the README.md.

## Overview

The implementation consists of two main binaries and supporting tools:

1. **validity-check** - Phase 1 capacity discovery
2. **microbenchmark** - Phase 2 full benchmark with ramp-up and steady-state
3. **Visualization tools** - Python script for post-analysis
4. **Grafana dashboard** - Real-time monitoring

## Project Structure

```
R2-bench/
├── types.go                    # Core data structures
├── validity_check.go           # Phase 1 capacity discovery
├── microbenchmark.go           # Phase 2 full benchmark
├── go.mod                      # Go module dependencies
├── Makefile                    # Build and run commands
├── requirements.txt            # Python dependencies
├── instances/                  # Storage client implementations
│   ├── r2.go                  # Cloudflare R2 client
│   ├── s3.go                  # AWS S3 client
│   └── ec2.go                 # EC2 monitoring
├── storage/                    # Data storage and metrics
│   ├── parquet.go             # Parquet file writer
│   └── prom.go                # Prometheus metrics
├── visualisation/              # Visualization tools
│   ├── visualizer.py          # Python analysis script
│   └── grafana.go             # Grafana dashboard generator
└── README.md                  # Original specification
```

## Quick Start

### 1. Prerequisites

- Go 1.21 or later
- Python 3.8+ with pip
- Cloudflare R2 account and credentials
- AWS EC2 instance (optional, for comparison)

### 2. Setup

```bash
# Clone and setup
cd R2-bench
make full-setup

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

Set up your R2 credentials:

```bash
export R2_ACCOUNT_ID="your-account-id"
export R2_ACCESS_KEY_ID="your-access-key-id"
export R2_SECRET_ACCESS_KEY="your-secret-access-key"
```

For AWS S3 comparison:

```bash
export AWS_ACCESS_KEY_ID="your-aws-access-key"
export AWS_SECRET_ACCESS_KEY="your-aws-secret-key"
export AWS_DEFAULT_REGION="eu-central-1"
```

### 4. Running the Benchmark

#### Phase 1: Capacity Discovery

```bash
./bin/validity-check \
  --url https://your-account.r2.cloudflarestorage.com \
  --instance c8gn.large \
  --bucket your-bucket-name \
  --object test-object-1gb \
  --range-size 104857600 \
  --concurrency 8 \
  --max-concurrency 64 \
  --output ./output
```

#### Phase 2: Full Benchmark

```bash
./bin/microbenchmark \
  --url https://your-account.r2.cloudflarestorage.com \
  --instance c8gn.large \
  --bucket your-bucket-name \
  --object test-object-1gb \
  --range-size 104857600 \
  --steady-state-hours 3 \
  --warmup-minutes 5 \
  --initial-concurrency 10 \
  --max-concurrency 200 \
  --output ./output \
  --prometheus-addr :9100
```

### 5. Visualization

After running the benchmark, analyze the results:

```bash
python3 visualisation/visualizer.py \
  ./output/r2-bench-*.parquet \
  --output-dir ./plots
```

## Implementation Details

### Core Components

#### 1. Storage Clients (`instances/`)

**R2 Client (`instances/r2.go`)**
- Implements S3-compatible API for Cloudflare R2
- Uses AWS SDK v2 with custom endpoint resolver
- Supports range requests, object uploads, and metadata queries

**S3 Client (`instances/s3.go`)**
- Standard AWS S3 client for comparison testing
- Uses AWS SDK v2 with configurable regions

**EC2 Monitor (`instances/ec2.go`)**
- Collects system metrics from `/proc` filesystem
- Monitors CPU, memory, network utilization
- Detects instance type and hardware characteristics

#### 2. Data Storage (`storage/`)

**Parquet Writer (`storage/parquet.go`)**
- Efficient columnar storage format for large datasets
- Batched writes for performance
- Structured schema matching the specification

**Prometheus Exporter (`storage/prom.go`)**
- Real-time metrics collection
- HTTP endpoint for Prometheus scraping
- Comprehensive metrics: throughput, latency, errors, system stats

#### 3. Benchmark Binaries

**Validity Check (`validity_check.go`)**
- Phase 1: Capacity discovery
- Tests concurrency levels from 8 to 64
- 5-minute test per concurrency level
- Creates test object if needed

**Microbenchmark (`microbenchmark.go`)**
- Phase 2: Full benchmark with three phases
- Warmup: 5 minutes at initial concurrency
- Ramp-up: Gradual concurrency increase
- Steady-state: Extended test at optimal concurrency
- Graceful shutdown handling

### Key Features

#### 1. Concurrency Management
- Dynamic worker pool management
- Gradual ramp-up to find optimal concurrency
- Connection reuse for efficiency
- Round-robin object key distribution

#### 2. Metrics Collection
- Per-request latency measurement
- Throughput calculation (Mbps)
- Error rate tracking
- System health monitoring
- Real-time Prometheus metrics

#### 3. Data Analysis
- Parquet format for efficient storage
- Python visualization with pandas/matplotlib
- Comprehensive plots: throughput, latency CDF, error rates
- Summary reports with key statistics

#### 4. Monitoring
- Grafana dashboard for real-time monitoring
- Prometheus metrics endpoint
- System health indicators
- Network utilization tracking

## Configuration Options

### Validity Check Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--url` | Required | Storage endpoint URL |
| `--instance` | Required | EC2 instance type |
| `--bucket` | Required | Bucket name |
| `--object` | test-object-1gb | Test object key |
| `--object-size` | 1GB | Object size in bytes |
| `--range-size` | 100MB | Range request size |
| `--concurrency` | 8 | Initial concurrency |
| `--max-concurrency` | 64 | Maximum concurrency to test |
| `--output` | ./output | Output directory |

### Benchmark Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--steady-state-hours` | 3 | Hours for steady-state test |
| `--warmup-minutes` | 5 | Warmup duration |
| `--ramp-step-minutes` | 1 | Ramp step duration |
| `--ramp-step-size` | 10 | Concurrency increase per step |
| `--initial-concurrency` | 10 | Initial concurrency level |
| `--max-concurrency` | 200 | Maximum concurrency |
| `--prometheus-addr` | :9100 | Prometheus metrics address |

## Output Files

### Parquet Files
- Location: `./output/r2-bench-YYYYMMDD-HHMMSS.parquet`
- Schema: Matches specification with all required columns
- Compression: Snappy for efficient storage

### Visualization Output
- Location: `./plots/`
- Files:
  - `throughput_timeline.png` - Throughput over time
  - `latency_cdf.png` - Latency cumulative distribution
  - `error_histogram.png` - HTTP status code distribution
  - `concurrency_analysis.png` - Performance vs concurrency
  - `system_health.png` - System metrics (if available)
  - `summary_report.txt` - Text summary

### Grafana Dashboard
- Location: `./grafana/r2-benchmark-dashboard.json`
- Import into Grafana for real-time monitoring
- Includes all key metrics panels

## Monitoring and Analysis

### Real-time Monitoring
1. Start the benchmark with Prometheus metrics enabled
2. Import the Grafana dashboard
3. Configure Prometheus to scrape metrics from `:9100`
4. View real-time performance data

### Post-analysis
1. Run the Python visualization script
2. Review generated plots and summary report
3. Analyze throughput, latency, and error patterns
4. Compare different concurrency levels

## Troubleshooting

### Common Issues

1. **R2 Credentials Not Found**
   - Ensure environment variables are set correctly
   - Check R2 account ID format

2. **Object Not Found**
   - The benchmark will create test objects automatically
   - Ensure bucket exists and is accessible

3. **High Error Rates**
   - Check network connectivity
   - Verify R2 rate limits
   - Monitor system resources

4. **Low Throughput**
   - Check EC2 instance type and network capacity
   - Verify object size is >512MB (bypasses CDN)
   - Monitor CPU and network utilization

### Performance Tuning

1. **Instance Selection**
   - Start with c8gn.large (100 Gbps)
   - Scale up to c8gn.4xlarge (200 Gbps) if needed
   - Monitor for network bottlenecks

2. **Concurrency Optimization**
   - Use validity check to find optimal concurrency
   - Balance throughput vs latency
   - Monitor error rates during ramp-up

3. **Network Optimization**
   - Use eu-central-1 region for EU buckets
   - Monitor TCP retransmits
   - Check link utilization

## Extending the Implementation

### Adding New Storage Providers
1. Implement the storage client interface in `instances/`
2. Add endpoint detection logic
3. Update client initialization in main binaries

### Custom Metrics
1. Extend the `RequestResult` struct in `types.go`
2. Update Parquet schema
3. Add Prometheus metrics in `storage/prom.go`

### Additional Visualizations
1. Extend the Python visualization script
2. Add new plot types
3. Update the Grafana dashboard

## Compliance with Specification

This implementation follows the README.md specification:

✅ **Phase 1**: Capacity discovery with concurrency ramp-up  
✅ **Phase 2**: Full benchmark with warmup, ramp-up, and steady-state  
✅ **Metrics**: Throughput, latency (P50/90/95/99), QPS, error rates  
✅ **Storage**: Parquet format with specified schema  
✅ **Monitoring**: Prometheus metrics and Grafana dashboard  
✅ **Constraints**: Respects R2 free tier limits  
✅ **Network**: Optimized for high-bandwidth transfers  
✅ **Analysis**: Comprehensive visualization and reporting  

The implementation provides a complete, production-ready benchmark suite for evaluating R2 performance against S3, with all the monitoring and analysis tools needed for comprehensive performance evaluation. 
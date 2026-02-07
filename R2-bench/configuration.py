"""
Configuration constants for the R2 benchmark experiment.

Architecture:
- One process per CPU core for maximum parallelism
- Each process runs async workers (coroutines)
- Each worker pipelines multiple HTTP requests
- Dynamic ramping: workers_per_core increases during ramp-up phase

Hierarchy:
- cores (vCPUs) - detected at runtime
- workers_per_core - starts at INITIAL_WORKERS_PER_CORE, ramps up
- total_workers = cores × workers_per_core
- concurrency = total_workers × pipeline_depth (HTTP requests in flight)
"""

import os

# =============================================================================
# CLOUD STORAGE CONFIGURATION
# =============================================================================

# Object storage configuration
BUCKET_NAME: str = os.getenv("BUCKET_NAME", "")

# AWS S3 credentials and configuration
S3_ENDPOINT: str = os.getenv("S3_ENDPOINT", "")
AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION: str = "eu-north-1"

# Cloudflare R2 credentials and configuration
R2_ENDPOINT: str = os.getenv("R2_ENDPOINT", "")
R2_ACCESS_KEY_ID: str = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY: str = os.getenv("R2_SECRET_ACCESS_KEY", "")

# =============================================================================
# TEST PARAMETERS
# =============================================================================

# Object configuration
OBJECT_SIZE_GB: int = 9
RANGE_SIZE_MB: int = 100
DEFAULT_OBJECT_KEY: str = "test-object-9gb"

# =============================================================================
# BENCHMARK PHASE CONFIGURATION
# =============================================================================

# Warm-up phase
WARM_UP_MINUTES: int = 1
INITIAL_WORKERS_PER_CORE: int = 8  # Start with 8 workers per core

# Ramp-up phase
RAMP_STEP_MINUTES: int = 5
RAMP_STEP_WORKERS_PER_CORE: int = 4  # Add 4 workers per core each step (reduced from 8 for gradual scaling)

# Steady state phase
STEADY_STATE_HOURS: int = 3

# =============================================================================
# ALGORITHM PARAMETERS
# =============================================================================

PLATEAU_THRESHOLD: float = 0.05  # Minimum improvement threshold (5%)
PEAK_DEGRADATION_THRESHOLD: float = 0.10  # Maximum degradation from peak (10%)
ERROR_RETRY_DELAY: int = 1  # Delay between retries in seconds
PROGRESS_INTERVAL: int = 50  # Log progress every N requests

# =============================================================================
# ERROR HANDLING AND TIMEOUTS
# =============================================================================

MAX_ERROR_RATE: float = 0.2  # 20% error rate threshold
MIN_REQUESTS_FOR_ERROR_CHECK: int = 10  # Minimum requests before checking error rate
MAX_CONSECUTIVE_ERRORS: int = 100  # Increased from 20 - for capacity discovery we want to push limits
MAX_RETRIES: int = 3  # Maximum number of retry attempts
ERROR_BACKOFF_ENABLED: bool = True  # Enable exponential backoff instead of stopping on errors
ERROR_BACKOFF_MAX_SECONDS: int = 5  # Maximum backoff delay (seconds)

# Request timeout configuration
# At high concurrency, R2 may queue requests, causing delays
# 60s allows for ~30s queue time + ~30s transfer time
REQUEST_TIMEOUT_SECONDS: int = 60  # 60 seconds for 100MB chunks (balanced for R2 queuing)

# =============================================================================
# HTTP STATUS CODES
# =============================================================================

HTTP_SUCCESS_STATUS: int = 200
HTTP_ERROR_STATUS: int = 500

# =============================================================================
# FILE SIZE CONSTANTS
# =============================================================================

BYTES_PER_MB: int = 1024 * 1024
BYTES_PER_GB: int = 1024 * 1024 * 1024
BITS_PER_BYTE: int = 8
GIGABITS_PER_GB: int = 1_000_000_000  # 1 Gigabit = 1,000,000,000 bits
SECONDS_PER_HOUR: int = 3600
SECONDS_PER_MINUTE: int = 60

# =============================================================================
# VISUALIZATION CONFIGURATION
# =============================================================================

THROUGHPUT_WINDOW_SIZE_SECONDS: float = 30.0  # Window size for throughput timeline plots
PER_SECOND_WINDOW_SIZE_SECONDS: float = 1.0  # Window size for per-second throughput calculations

# =============================================================================
# WORKER POOL CONFIGURATION
# =============================================================================

# Per-core limits
MAX_WORKERS_PER_CORE: int = 256  # Maximum async workers per core (safety limit for memory)

# Pipeline configuration
PIPELINE_DEPTH: int = 3  # Number of in-flight HTTP requests per worker

# Executor threads (for blocking disk I/O only)
EXECUTOR_THREADS_PER_CORE: int = 2  # Minimal threads for disk writes

# Persistence configuration
PERSISTENCE_BATCH_SIZE: int = 200  # Number of records to batch before writing
PERSISTENCE_FLUSH_INTERVAL_SECONDS: float = 15.0  # Flush to disk every 15s to free memory (reduced from 30s for aggressive memory management)
CONSOLIDATION_BATCH_SIZE: int = 50  # Number of parquet files to process per batch during consolidation (reduces memory usage)

# Network configuration
CONNECTION_POOL_SAFETY_FACTOR: float = 1.5  # Safety factor for boto3 connection pool sizing

# SSL Configuration
# Disabling SSL removes encryption overhead (~30-50% CPU), enabling 40-50 Gbps throughput
# Safe for benchmarking with synthetic test data (random 9GB object)
# Re-enable (set to False) if testing with sensitive/production data or compliance requirements
DISABLE_SSL_VERIFICATION: bool = True  # True = max throughput, False = encrypted transfers

# Benchmark control
BANDWIDTH_UTILIZATION_THRESHOLD: float = 0.95  # Stop ramping at 95% of bandwidth

# =============================================================================
# CLI DEFAULTS
# =============================================================================

DEFAULT_OUTPUT_DIR: str = "results"
DEFAULT_PLOTS_DIR: str = "plots"

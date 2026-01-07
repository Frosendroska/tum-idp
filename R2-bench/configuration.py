"""
Configuration constants for the R2 benchmark experiment.

This module contains all configuration parameters including:
- Cloud credentials and endpoints
- Instance type configurations with bandwidth limits
- Test parameters (object sizes, concurrency settings)
- Algorithm parameters (thresholds, timeouts)
- File size constants and conversion factors
"""

import os
from typing import Dict

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
INITIAL_CONCURRENCY: int = 8

# Ramp-up phase
RAMP_STEP_MINUTES: int = 5
RAMP_STEP_CONCURRENCY: int = 8

# Steady state phase
STEADY_STATE_HOURS: int = 3

# =============================================================================
# ALGORITHM PARAMETERS
# =============================================================================

PLATEAU_THRESHOLD: float = 0.05  # Minimum improvement threshold for plateau detection (5%)
PEAK_DEGRADATION_THRESHOLD: float = 0.10  # Maximum degradation from historical peak (10%)
ERROR_RETRY_DELAY: int = 1  # Delay between retries in seconds
PROGRESS_INTERVAL: int = 50  # Log progress every N requests

# =============================================================================
# ERROR HANDLING AND TIMEOUTS
# =============================================================================

MAX_ERROR_RATE: float = 0.2  # 20% error rate threshold
MIN_REQUESTS_FOR_ERROR_CHECK: int = 10  # Minimum requests before checking error rate
MAX_CONSECUTIVE_ERRORS: int = 20  # Stop after this many consecutive errors
MAX_RETRIES: int = 3  # Maximum number of retry attempts

# Request timeout configuration (4x longer for 100MB chunks)
REQUEST_TIMEOUT_SECONDS: int = 120

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

PERSISTENCE_FLUSH_INTERVAL_SECONDS: float = 1.0  # Flush interval for persistence queue

WORKERS_PER_PROCESS: int = 8  # Number of async workers (coroutines) per process
PIPELINE_DEPTH: int = 3  # Number of in-flight requests per worker
EXECUTOR_THREADS_RATIO: float = 2.0  # Ratio for calculating executor threads: threads = workers × ratio

# Max concurrency calculation: max_concurrency = (bandwidth_gbps × RTT × safety_factor) / request_size_gb
MAX_CONCURRENCY_RTT_SECONDS: float = 0.1  # 100ms round-trip time
MAX_CONCURRENCY_SAFETY_FACTOR: float = 2.0  # Safety factor for max concurrency calculation
REQUEST_SIZE_GB: float = 0.8  # 100MB = 0.8 Gb

CONNECTION_POOL_SAFETY_FACTOR: float = 1.5  # Safety factor for boto3 connection pool sizing
BANDWIDTH_UTILIZATION_THRESHOLD: float = 0.95  # Stop ramping at 95% of bandwidth
PERSISTENCE_BATCH_SIZE: int = 200  # Number of records to batch before writing

# =============================================================================
# CLI DEFAULTS
# =============================================================================

DEFAULT_OUTPUT_DIR: str = "results"
DEFAULT_PLOTS_DIR: str = "plots"

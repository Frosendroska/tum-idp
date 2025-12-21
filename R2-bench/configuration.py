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
# EC2 INSTANCE CONFIGURATIONS
# =============================================================================

# Maps instance type to vCPUs and maximum network bandwidth
# Used for automatic bandwidth detection based on instance type
INSTANCE_CONFIGS: Dict[str, Dict[str, int]] = {
    "r5.xlarge": {
        "vcpus": 4,
        "max_bandwidth_gbps": 10,
    },
    "c5n.9xlarge": {
        "vcpus": 36,
        "max_bandwidth_gbps": 50,
    },
    "c6in.16xlarge": {
        "vcpus": 64,
        "max_bandwidth_gbps": 100,
    },
    "hpc7g.16xlarge": {
        "vcpus": 64,
        "max_bandwidth_gbps": 200,
    },
}

# Default system bandwidth limit (fallback when instance type not specified)
SYSTEM_BANDWIDTH_GBPS: float = 25.0

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
RAMP_STEP_CONCURRENCY: int = 32
MAX_CONCURRENCY: int = 400

# Steady state phase
STEADY_STATE_HOURS: int = 3

# =============================================================================
# ALGORITHM PARAMETERS
# =============================================================================

PLATEAU_THRESHOLD: float = 0.2  # Minimum improvement threshold for plateau detection
PEAK_DEGRADATION_THRESHOLD: float = 0.5  # Maximum degradation from historical peak
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
# WORKER POOL DEFAULTS
# =============================================================================

DEFAULT_MAX_WORKERS: int = 500  # Default maximum number of workers
DEFAULT_PERSISTENCE_BATCH_SIZE: int = 100  # Default batch size for persistence
PERSISTENCE_FLUSH_INTERVAL_SECONDS: float = 1.0  # Flush interval for persistence queue

# =============================================================================
# CLI DEFAULTS
# =============================================================================

DEFAULT_OUTPUT_DIR: str = "results"
DEFAULT_PLOTS_DIR: str = "plots"

# =============================================================================
# ALGORITHM DEFAULTS
# =============================================================================

DEFAULT_MAX_CONCURRENCY_RAMP: int = 100  # Default max concurrency for ramp algorithm

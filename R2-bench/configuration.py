"""
Configuration constants for the R2 benchmark experiment.
"""
import os

# Object storage configuration
BUCKET_NAME = os.getenv('BUCKET_NAME', '')

# Common credentials
S3_ENDPOINT = os.getenv('S3_ENDPOINT', '')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', '')
AWS_REGION = 'eu-central-1'

R2_ENDPOINT = os.getenv('R2_ENDPOINT', '')
R2_ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID', '')
R2_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY', '')

# System bandwidth limits
SYSTEM_BANDWIDTH_MBPS = 25000  # Total system bandwidth limit for single EC2 instance

# Test parameters
OBJECT_SIZE_GB = 9
RANGE_SIZE_MB = 100
DEFAULT_OBJECT_KEY = "test-object-9gb"

# Benchmark phases
WARM_UP_MINUTES = 1
INITIAL_CONCURRENCY = 8

RAMP_STEP_MINUTES = 5  
RAMP_STEP_CONCURRENCY = 32  
MAX_CONCURRENCY = 400  # Reduced from 1280 - R2 connection limits  

STEADY_STATE_HOURS = 3

# Algorithm parameters
PLATEAU_THRESHOLD = 0.2
PEAK_DEGRADATION_THRESHOLD = 0.5  # For degradation from historical peak
ERROR_RETRY_DELAY = 1
PROGRESS_INTERVAL = 50  # Log progress every N requests

# CLI defaults
DEFAULT_OUTPUT_DIR = "results"
DEFAULT_PLOTS_DIR = "plots"

# Error handling and termination
MAX_ERROR_RATE = 0.2  # 20% error rate threshold
MIN_REQUESTS_FOR_ERROR_CHECK = 10  # Minimum requests before checking error rate
MAX_CONSECUTIVE_ERRORS = 20  # Stop after this many consecutive errors
MAX_RETRIES = 3

# Logging configuration

# HTTP status codes
HTTP_SUCCESS_STATUS = 200
HTTP_ERROR_STATUS = 500

# File size constants
BYTES_PER_MB = 1024 * 1024
BYTES_PER_GB = 1024 * 1024 * 1024
BITS_PER_BYTE = 8
MEGABITS_PER_MB = 1_000_000
SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60
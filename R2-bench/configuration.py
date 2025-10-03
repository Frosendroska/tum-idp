"""
Configuration constants for the R2 benchmark experiment.
"""

# Object storage configuration
R2_ENDPOINT = 'https://0a3675349f63db3e1f510c90ed0002ce.r2.cloudflarestorage.com'
S3_ENDPOINT = 'https://s3.eu-central-1.amazonaws.com'
BUCKET_NAME = 'idp-bucket'

# Common credentials
AWS_ACCESS_KEY_ID = '14675cbcde7c6f12dfd15cd3949b0310'
AWS_SECRET_ACCESS_KEY = '18e5fb95377340203c42e28d395861f277b94a9c5dfb755c6f74cd18f7e38129'

# AWS configuration
AWS_REGION = 'eu-central-1'

# System bandwidth limits
SYSTEM_BANDWIDTH_MBPS = 100  # Total system bandwidth limit for single EC2 instance

# Test parameters
OBJECT_SIZE_GB = 9
RANGE_SIZE_MB = 100
DEFAULT_OBJECT_KEY = "test-object-9gb"

# Benchmark phases
WARM_UP_MINUTES = 1
INITIAL_CONCURRENCY = 8

RAMP_STEP_MINUTES = 1  
RAMP_STEP_CONCURRENCY = 64  
MAX_CONCURRENCY = 128  

STEADY_STATE_HOURS = 3

# Algorithm parameters
PLATEAU_THRESHOLD = 0.05
ERROR_RETRY_DELAY = 1
PROGRESS_INTERVAL = 100  # Log progress every N requests

# CLI defaults
DEFAULT_OUTPUT_DIR = "results"
DEFAULT_PLOTS_DIR = "plots"

# Error handling and termination
MAX_ERROR_RATE = 0.5  # 50% error rate threshold
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
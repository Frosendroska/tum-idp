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

# Test parameters
OBJECT_SIZE_GB = 1
RANGE_SIZE_MB = 100
DEFAULT_OBJECT_KEY = "test-object-9gb"

# Benchmark phases
WARM_UP_MINUTES = 0.1
INITIAL_CONCURRENCY = 8
RAMP_STEP_CONCURRENCY = 64  
STEADY_STATE_HOURS = 3

# Worker bandwidth limits
WORKER_BANDWIDTH_MBPS = 10  # Current worker bandwith

# CLI defaults
DEFAULT_OUTPUT_DIR = "results"
DEFAULT_PLOTS_DIR = "plots"

# Algorithm parameters
PLATEAU_THRESHOLD = 0.05
RAMP_STEP_SECONDS = 10  
MAX_CONCURRENCY = 128  
ERROR_RETRY_DELAY = 1
PROGRESS_REPORT_INTERVAL = 60  # seconds
PROGRESS_MONITOR_INTERVAL = 10  # seconds

# Error handling and termination
MAX_ERROR_RATE = 0.5  # 50% error rate threshold
MIN_REQUESTS_FOR_ERROR_CHECK = 10  # Minimum requests before checking error rate
MAX_CONSECUTIVE_ERRORS = 20  # Stop after this many consecutive errors

# Logging configuration
LOG_REQUESTS_INTERVAL = 100  # Log progress every N requests

# Test data generation
CHUNK_SIZE_MB = 100  # Same as RANGE_SIZE_MB for consistency
TEST_OBJECT_SIZE_GB = 9  # Default test object size

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
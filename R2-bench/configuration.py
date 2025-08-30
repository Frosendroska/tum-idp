"""
Configuration constants for the R2 benchmark experiment.
"""

# Object storage configuration
R2_ENDPOINT = 'https://<ACCOUNT_ID>.r2.cloudflarestorage.com'
S3_ENDPOINT = 'https://s3.eu-central-1.amazonaws.com'
BUCKET_NAME = 'r2-benchmark-bucket'

# AWS credentials
AWS_ACCESS_KEY_ID = 'your_aws_access_key_here'
AWS_SECRET_ACCESS_KEY = 'your_aws_secret_key_here'
AWS_REGION = 'eu-central-1'

# Test parameters
OBJECT_SIZE_GB = 1
RANGE_SIZE_MB = 100

# Benchmark phases
WARM_UP_MINUTES = 5
RAMP_STEP_MINUTES = 5
RAMP_STEP_CONCURRENCY = 8
STEADY_STATE_HOURS = 3

# EC2 instance types
EC2_INSTANCE = "c8gn.large"
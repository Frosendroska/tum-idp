# R2 Benchmark Makefile

.PHONY: help build clean test validity-check benchmark visualization grafana-dashboard install-deps

# Default target
help:
	@echo "R2 Benchmark - Available targets:"
	@echo "  build              - Build all binaries"
	@echo "  validity-check     - Build validity check binary"
	@echo "  benchmark          - Build benchmark binary"
	@echo "  visualization      - Build visualization tools"
	@echo "  grafana-dashboard  - Generate Grafana dashboard"
	@echo "  clean              - Clean build artifacts"
	@echo "  install-deps       - Install Go dependencies"
	@echo "  test               - Run tests"

# Build all binaries
build: validity-check benchmark visualization grafana-dashboard

# Build validity check binary
validity-check:
	@echo "Building validity check binary..."
	go build -o bin/validity-check validity_check.go

# Build benchmark binary
benchmark:
	@echo "Building benchmark binary..."
	go build -o bin/microbenchmark microbenchmark.go

# Build visualization tools
visualization:
	@echo "Building visualization tools..."
	cd visualisation && go build -o ../bin/grafana-dashboard grafana.go

# Generate Grafana dashboard
grafana-dashboard:
	@echo "Generating Grafana dashboard..."
	@mkdir -p grafana
	cd visualisation && go run grafana.go

# Install Go dependencies
install-deps:
	@echo "Installing Go dependencies..."
	go mod download
	go mod tidy

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf bin/
	rm -rf output/
	rm -rf plots/
	rm -rf grafana/

# Run tests
test:
	@echo "Running tests..."
	go test ./...

# Create necessary directories
setup:
	@echo "Setting up directories..."
	mkdir -p bin/
	mkdir -p output/
	mkdir -p plots/
	mkdir -p grafana/

# Example commands for running benchmarks
example-validity-check:
	@echo "Example validity check command:"
	@echo "./bin/validity-check \\"
	@echo "  --url https://your-account.r2.cloudflarestorage.com \\"
	@echo "  --instance c8gn.large \\"
	@echo "  --bucket your-bucket-name \\"
	@echo "  --object test-object-1gb \\"
	@echo "  --range-size 104857600 \\"
	@echo "  --concurrency 8 \\"
	@echo "  --max-concurrency 64 \\"
	@echo "  --output ./output"

example-benchmark:
	@echo "Example benchmark command:"
	@echo "./bin/microbenchmark \\"
	@echo "  --url https://your-account.r2.cloudflarestorage.com \\"
	@echo "  --instance c8gn.large \\"
	@echo "  --bucket your-bucket-name \\"
	@echo "  --object test-object-1gb \\"
	@echo "  --range-size 104857600 \\"
	@echo "  --steady-state-hours 3 \\"
	@echo "  --warmup-minutes 5 \\"
	@echo "  --initial-concurrency 10 \\"
	@echo "  --max-concurrency 200 \\"
	@echo "  --output ./output \\"
	@echo "  --prometheus-addr :9100"

example-visualization:
	@echo "Example visualization command:"
	@echo "python3 visualisation/visualizer.py \\"
	@echo "  ./output/r2-bench-*.parquet \\"
	@echo "  --output-dir ./plots"

# Environment setup help
env-help:
	@echo "Required environment variables for R2:"
	@echo "  export R2_ACCOUNT_ID=your-account-id"
	@echo "  export R2_ACCESS_KEY_ID=your-access-key-id"
	@echo "  export R2_SECRET_ACCESS_KEY=your-secret-access-key"
	@echo ""
	@echo "For AWS S3 comparison:"
	@echo "  export AWS_ACCESS_KEY_ID=your-aws-access-key"
	@echo "  export AWS_SECRET_ACCESS_KEY=your-aws-secret-key"
	@echo "  export AWS_DEFAULT_REGION=eu-central-1"

# Full setup including dependencies
full-setup: install-deps setup build
	@echo "Full setup completed!"
	@echo "Run 'make env-help' to see required environment variables"
	@echo "Run 'make example-validity-check' to see example commands" 
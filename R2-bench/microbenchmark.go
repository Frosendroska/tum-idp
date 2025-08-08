package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"math/rand"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"r2-bench/instances"
	"r2-bench/storage"
)

var (
	url              = flag.String("url", "", "Storage endpoint URL (r2 or s3)")
	instanceType     = flag.String("instance", "", "EC2 instance type")
	bucketName       = flag.String("bucket", "", "Bucket name")
	objectKey        = flag.String("object", "test-object-1gb", "Object key for testing")
	objectSize       = flag.Int64("object-size", 1024*1024*1024, "Object size in bytes (default: 1GB)")
	rangeSize        = flag.Int64("range-size", 100*1024*1024, "Range size in bytes (default: 100MB)")
	steadyStateHours = flag.Int("steady-state-hours", 3, "Hours to run steady state test")
	warmupMinutes    = flag.Int("warmup-minutes", 5, "Warmup duration in minutes")
	rampStepMinutes  = flag.Int("ramp-step-minutes", 1, "Ramp step duration in minutes")
	rampStepSize     = flag.Int("ramp-step-size", 10, "Concurrency increase per ramp step")
	initialConcurrency = flag.Int("initial-concurrency", 10, "Initial concurrency level")
	maxConcurrency   = flag.Int("max-concurrency", 200, "Maximum concurrency to test")
	outputDir        = flag.String("output", "./output", "Output directory for results")
	prometheusAddr   = flag.String("prometheus-addr", ":9100", "Prometheus metrics server address")
)

// BenchmarkRunner manages the benchmark execution
type BenchmarkRunner struct {
	client        interface {
		GetObjectRange(ctx context.Context, objectKey string, start, length int64) ([]byte, error)
		ObjectExists(ctx context.Context, objectKey string) (bool, error)
		GetEndpoint() string
	}
	ec2Monitor    *instances.EC2Monitor
	parquetWriter *storage.ParquetWriter
	promExporter  *storage.PrometheusExporter
	config        *Config
	results       chan RequestResult
	stopChan      chan struct{}
	wg            sync.WaitGroup
}

func main() {
	flag.Parse()

	if *url == "" || *instanceType == "" || *bucketName == "" {
		log.Fatal("URL, instance type, and bucket name are required")
	}

	log.Printf("Starting R2 benchmark for %s on %s", *url, *instanceType)
	log.Printf("Object: %s (%d bytes), Range size: %d bytes", *objectKey, *objectSize, *rangeSize)
	log.Printf("Steady state: %d hours, Warmup: %d minutes", *steadyStateHours, *warmupMinutes)

	// Initialize components
	runner, err := initializeBenchmark()
	if err != nil {
		log.Fatalf("Failed to initialize benchmark: %v", err)
	}
	defer runner.cleanup()

	// Start Prometheus server
	go func() {
		log.Printf("Starting Prometheus server on %s", *prometheusAddr)
		if err := runner.promExporter.StartServer(*prometheusAddr); err != nil {
			log.Printf("Prometheus server error: %v", err)
		}
	}()

	// Handle graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-sigChan
		log.Printf("Received shutdown signal, stopping benchmark...")
		close(runner.stopChan)
	}()

	// Run benchmark phases
	runner.runBenchmark()
}

func initializeBenchmark() (*BenchmarkRunner, error) {
	// Initialize storage client
	var client interface {
		GetObjectRange(ctx context.Context, objectKey string, start, length int64) ([]byte, error)
		ObjectExists(ctx context.Context, objectKey string) (bool, error)
		GetEndpoint() string
	}

	var err error
	if isR2Endpoint(*url) {
		// Parse R2 credentials from environment
		accountID := os.Getenv("R2_ACCOUNT_ID")
		accessKeyID := os.Getenv("R2_ACCESS_KEY_ID")
		secretAccessKey := os.Getenv("R2_SECRET_ACCESS_KEY")

		if accountID == "" || accessKeyID == "" || secretAccessKey == "" {
			return nil, fmt.Errorf("R2 credentials not found in environment variables")
		}

		client, err = instances.NewR2Client(accountID, accessKeyID, secretAccessKey, *bucketName)
		if err != nil {
			return nil, fmt.Errorf("failed to create R2 client: %v", err)
		}
	} else {
		// S3 client
		region := extractRegionFromURL(*url)
		client, err = instances.NewS3Client(region, *bucketName)
		if err != nil {
			return nil, fmt.Errorf("failed to create S3 client: %v", err)
		}
	}

	// Initialize EC2 monitor
	ec2Monitor, err := instances.NewEC2Monitor()
	if err != nil {
		log.Printf("Warning: Failed to initialize EC2 monitor: %v", err)
	}

	// Initialize Parquet writer
	parquetWriter, err := storage.NewParquetWriter(*outputDir, 1000)
	if err != nil {
		return nil, fmt.Errorf("failed to create Parquet writer: %v", err)
	}

	// Initialize Prometheus exporter
	promExporter := storage.NewPrometheusExporter()

	// Create configuration
	config := &Config{
		URL:              *url,
		InstanceType:     *instanceType,
		RangeSize:        *rangeSize,
		SteadyStateHours: *steadyStateHours,
		BucketName:       *bucketName,
		ObjectKey:        *objectKey,
		ObjectSize:       *objectSize,
		WarmupMinutes:    *warmupMinutes,
		RampStepMinutes:  *rampStepMinutes,
		RampStepSize:     *rampStepSize,
		MaxConcurrency:   *maxConcurrency,
	}

	return &BenchmarkRunner{
		client:        client,
		ec2Monitor:    ec2Monitor,
		parquetWriter: parquetWriter,
		promExporter:  promExporter,
		config:        config,
		results:       make(chan RequestResult, 10000),
		stopChan:      make(chan struct{}),
	}, nil
}

func (br *BenchmarkRunner) cleanup() {
	close(br.results)
	br.wg.Wait()
	br.parquetWriter.Close()
}

func (br *BenchmarkRunner) runBenchmark() {
	ctx := context.Background()

	// Verify test object exists
	exists, err := br.client.ObjectExists(ctx, br.config.ObjectKey)
	if err != nil {
		log.Fatalf("Failed to check object existence: %v", err)
	}
	if !exists {
		log.Fatalf("Test object %s does not exist", br.config.ObjectKey)
	}

	// Start result collector
	go br.collectResults()

	// Phase 1: Warmup
	log.Printf("Phase 1: Warmup for %d minutes at concurrency %d", br.config.WarmupMinutes, *initialConcurrency)
	br.runPhase(ctx, *initialConcurrency, time.Duration(br.config.WarmupMinutes)*time.Minute, "warmup")

	// Phase 2: Ramp-up
	log.Printf("Phase 2: Ramp-up from %d to %d concurrency", *initialConcurrency, br.config.MaxConcurrency)
	br.runRampUp(ctx, *initialConcurrency, br.config.MaxConcurrency)

	// Phase 3: Steady state
	optimalConcurrency := br.findOptimalConcurrency()
	log.Printf("Phase 3: Steady state for %d hours at concurrency %d", br.config.SteadyStateHours, optimalConcurrency)
	br.runPhase(ctx, optimalConcurrency, time.Duration(br.config.SteadyStateHours)*time.Hour, "steady-state")

	log.Printf("Benchmark completed successfully")
}

func (br *BenchmarkRunner) runPhase(ctx context.Context, concurrency int, duration time.Duration, phase string) {
	log.Printf("Starting %s phase with concurrency %d for %v", phase, concurrency, duration)

	startTime := time.Now()
	endTime := startTime.Add(duration)

	// Start workers
	for i := 0; i < concurrency; i++ {
		br.wg.Add(1)
		go br.worker(ctx, i, concurrency, endTime)
	}

	// Monitor and collect metrics
	go br.monitorPhase(concurrency, startTime, endTime)

	// Wait for phase completion or stop signal
	select {
	case <-time.After(duration):
		log.Printf("%s phase completed", phase)
	case <-br.stopChan:
		log.Printf("%s phase stopped by user", phase)
	}

	// Stop workers
	br.wg.Wait()
}

func (br *BenchmarkRunner) runRampUp(ctx context.Context, startConcurrency, maxConcurrency int) {
	currentConcurrency := startConcurrency
	stepDuration := time.Duration(br.config.RampStepMinutes) * time.Minute

	for currentConcurrency <= maxConcurrency {
		log.Printf("Ramp step: testing concurrency %d for %v", currentConcurrency, stepDuration)
		
		startTime := time.Now()
		endTime := startTime.Add(stepDuration)

		// Start workers for this step
		for i := 0; i < currentConcurrency; i++ {
			br.wg.Add(1)
			go br.worker(ctx, i, currentConcurrency, endTime)
		}

		// Monitor this step
		go br.monitorPhase(currentConcurrency, startTime, endTime)

		// Wait for step completion or stop signal
		select {
		case <-time.After(stepDuration):
			log.Printf("Ramp step %d completed", currentConcurrency)
		case <-br.stopChan:
			log.Printf("Ramp stopped by user at concurrency %d", currentConcurrency)
			return
		}

		// Stop workers for this step
		br.wg.Wait()

		// Increase concurrency for next step
		currentConcurrency += br.config.RampStepSize
	}
}

func (br *BenchmarkRunner) findOptimalConcurrency() int {
	// This is a simplified implementation
	// In practice, you'd analyze the metrics collected during ramp-up
	// to find the concurrency level that provides the best throughput
	// without causing excessive latency or errors
	
	// For now, return a reasonable default
	return 50
}

func (br *BenchmarkRunner) worker(ctx context.Context, threadID, concurrency int, endTime time.Time) {
	defer br.wg.Done()

	for time.Now().Before(endTime) {
		select {
		case <-br.stopChan:
			return
		default:
		}

		// Generate random range within object bounds
		maxStart := br.config.ObjectSize - br.config.RangeSize
		if maxStart <= 0 {
			log.Printf("Range size %d is larger than object size %d", br.config.RangeSize, br.config.ObjectSize)
			return
		}

		rangeStart := rand.Int63n(maxStart)
		rangeLen := br.config.RangeSize
		if rangeStart+rangeLen > br.config.ObjectSize {
			rangeLen = br.config.ObjectSize - rangeStart
		}

		// Make request
		reqStart := time.Now()
		data, err := br.client.GetObjectRange(ctx, br.config.ObjectKey, rangeStart, rangeLen)
		latency := time.Since(reqStart)

		// Record result
		result := RequestResult{
			Timestamp:    reqStart,
			ThreadID:     threadID,
			ConnID:       threadID % concurrency,
			ObjectKey:    br.config.ObjectKey,
			RangeStart:   rangeStart,
			RangeLen:     rangeLen,
			Bytes:        int64(len(data)),
			LatencyMs:    float64(latency.Microseconds()) / 1000.0,
			HTTPStatus:   200,
			RetryCount:   0,
			InstanceType: br.config.InstanceType,
			Concurrency:  concurrency,
		}

		if err != nil {
			result.ErrMsg = err.Error()
			result.HTTPStatus = 500
		}

		// Send result
		select {
		case br.results <- result:
		default:
			log.Printf("Warning: Results channel full, dropping result")
		}
	}
}

func (br *BenchmarkRunner) collectResults() {
	for result := range br.results {
		// Write to Parquet
		if err := br.parquetWriter.WriteResult(result); err != nil {
			log.Printf("Error writing result: %v", err)
		}

		// Update Prometheus metrics
		br.promExporter.RecordRequest(
			result.InstanceType,
			result.Concurrency,
			result.LatencyMs,
			result.HTTPStatus,
			result.ErrMsg,
		)
	}
}

func (br *BenchmarkRunner) monitorPhase(concurrency int, startTime, endTime time.Time) {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	for time.Now().Before(endTime) {
		select {
		case <-ticker.C:
			// Update Prometheus metrics
			br.promExporter.UpdateConcurrency(br.config.InstanceType, concurrency)

			// Collect system stats if available
			if br.ec2Monitor != nil {
				if stats, err := br.ec2Monitor.GetSystemStats(); err == nil {
					br.promExporter.UpdateCPUStats(br.config.InstanceType, stats.CPUUtilization)
					if stats.NetworkStats != nil {
						br.promExporter.UpdateNetworkStats(
							br.config.InstanceType,
							stats.NetworkStats.LinkUtilPct,
							float64(stats.NetworkStats.Retransmits),
						)
					}
				}
			}
		case <-br.stopChan:
			return
		}
	}
}

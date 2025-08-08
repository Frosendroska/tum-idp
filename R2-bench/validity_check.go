package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"math/rand"
	"os"
	"sync"
	"time"

	"r2-bench/instances"
	"r2-bench/storage"
)

var (
	url          = flag.String("url", "", "Storage endpoint URL (r2 or s3)")
	instanceType = flag.String("instance", "", "EC2 instance type")
	bucketName   = flag.String("bucket", "", "Bucket name")
	objectKey    = flag.String("object", "test-object-1gb", "Object key for testing")
	objectSize   = flag.Int64("object-size", 1024*1024*1024, "Object size in bytes (default: 1GB)")
	rangeSize    = flag.Int64("range-size", 100*1024*1024, "Range size in bytes (default: 100MB)")
	concurrency  = flag.Int("concurrency", 8, "Initial concurrency level")
	maxConcurrency = flag.Int("max-concurrency", 64, "Maximum concurrency to test")
	outputDir    = flag.String("output", "./output", "Output directory for results")
)

func main() {
	flag.Parse()

	if *url == "" || *instanceType == "" || *bucketName == "" {
		log.Fatal("URL, instance type, and bucket name are required")
	}

	log.Printf("Starting validity check for %s on %s", *url, *instanceType)
	log.Printf("Object: %s (%d bytes), Range size: %d bytes", *objectKey, *objectSize, *rangeSize)

	// Initialize storage client
	var client interface {
		GetObjectRange(ctx context.Context, objectKey string, start, length int64) ([]byte, error)
		ObjectExists(ctx context.Context, objectKey string) (bool, error)
		UploadObject(ctx context.Context, objectKey string, data []byte) error
		GetEndpoint() string
	}

	var err error
	if isR2Endpoint(*url) {
		// Parse R2 credentials from environment
		accountID := os.Getenv("R2_ACCOUNT_ID")
		accessKeyID := os.Getenv("R2_ACCESS_KEY_ID")
		secretAccessKey := os.Getenv("R2_SECRET_ACCESS_KEY")

		if accountID == "" || accessKeyID == "" || secretAccessKey == "" {
			log.Fatal("R2 credentials not found in environment variables")
		}

		client, err = instances.NewR2Client(accountID, accessKeyID, secretAccessKey, *bucketName)
		if err != nil {
			log.Fatalf("Failed to create R2 client: %v", err)
		}
	} else {
		// S3 client
		region := extractRegionFromURL(*url)
		client, err = instances.NewS3Client(region, *bucketName)
		if err != nil {
			log.Fatalf("Failed to create S3 client: %v", err)
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
		log.Fatalf("Failed to create Parquet writer: %v", err)
	}
	defer parquetWriter.Close()

	// Check if test object exists, create if not
	ctx := context.Background()
	exists, err := client.ObjectExists(ctx, *objectKey)
	if err != nil {
		log.Fatalf("Failed to check object existence: %v", err)
	}

	if !exists {
		log.Printf("Test object does not exist, creating...")
		if err := createTestObject(ctx, client, *objectKey, *objectSize); err != nil {
			log.Fatalf("Failed to create test object: %v", err)
		}
		log.Printf("Test object created successfully")
	}

	// Run capacity discovery
	runCapacityDiscovery(ctx, client, ec2Monitor, parquetWriter)
}

func isR2Endpoint(url string) bool {
	return contains(url, "r2.cloudflarestorage.com")
}

func extractRegionFromURL(url string) string {
	// Simple region extraction for S3 URLs
	// In practice, you might want more sophisticated parsing
	if contains(url, "eu-central-1") {
		return "eu-central-1"
	}
	return "us-east-1" // default
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || (len(s) > len(substr) && 
		(s[:len(substr)] == substr || s[len(s)-len(substr):] == substr || 
		contains(s[1:len(s)-1], substr))))
}

func createTestObject(ctx context.Context, client interface {
	UploadObject(ctx context.Context, objectKey string, data []byte) error
}, objectKey string, objectSize int64) error {
	// Create test data (random bytes)
	data := make([]byte, objectSize)
	rand.Read(data)

	log.Printf("Uploading %d bytes to %s...", objectSize, objectKey)
	start := time.Now()
	
	if err := client.UploadObject(ctx, objectKey, data); err != nil {
		return err
	}
	
	duration := time.Since(start)
	throughput := float64(objectSize) / duration.Seconds() / (1024 * 1024) // MB/s
	log.Printf("Upload completed in %v (%.2f MB/s)", duration, throughput)
	
	return nil
}

func runCapacityDiscovery(ctx context.Context, client interface {
	GetObjectRange(ctx context.Context, objectKey string, start, length int64) ([]byte, error)
}, ec2Monitor *instances.EC2Monitor, parquetWriter *storage.ParquetWriter) {
	log.Printf("Starting capacity discovery with concurrency levels: %d to %d", *concurrency, *maxConcurrency)

	var wg sync.WaitGroup
	results := make(chan RequestResult, 1000)
	
	// Start result collector
	go collectResults(results, parquetWriter)

	// Test different concurrency levels
	for c := *concurrency; c <= *maxConcurrency; c += 8 {
		log.Printf("Testing concurrency level: %d", c)
		
		// Run test for 5 minutes per concurrency level
		testDuration := 5 * time.Minute
		startTime := time.Now()
		
		// Start worker goroutines
		for i := 0; i < c; i++ {
			wg.Add(1)
			go worker(ctx, client, i, c, results, &wg, startTime, testDuration)
		}
		
		// Wait for test duration
		time.Sleep(testDuration)
		
		// Stop workers
		wg.Wait()
		
		log.Printf("Completed concurrency level %d", c)
	}
	
	close(results)
	log.Printf("Capacity discovery completed")
}

func worker(ctx context.Context, client interface {
	GetObjectRange(ctx context.Context, objectKey string, start, length int64) ([]byte, error)
}, threadID, concurrency int, results chan<- RequestResult, wg *sync.WaitGroup, startTime time.Time, duration time.Duration) {
	defer wg.Done()
	
	endTime := startTime.Add(duration)
	
	for time.Now().Before(endTime) {
		// Generate random range within object bounds
		maxStart := *objectSize - *rangeSize
		if maxStart <= 0 {
			log.Printf("Range size %d is larger than object size %d", *rangeSize, *objectSize)
			return
		}
		
		rangeStart := rand.Int63n(maxStart)
		rangeLen := *rangeSize
		if rangeStart + rangeLen > *objectSize {
			rangeLen = *objectSize - rangeStart
		}
		
		// Make request
		reqStart := time.Now()
		data, err := client.GetObjectRange(ctx, *objectKey, rangeStart, rangeLen)
		latency := time.Since(reqStart)
		
		// Record result
		result := RequestResult{
			Timestamp:    reqStart,
			ThreadID:     threadID,
			ConnID:       threadID % concurrency,
			ObjectKey:    *objectKey,
			RangeStart:   rangeStart,
			RangeLen:     rangeLen,
			Bytes:        int64(len(data)),
			LatencyMs:    float64(latency.Microseconds()) / 1000.0,
			HTTPStatus:   200,
			RetryCount:   0,
			InstanceType: *instanceType,
			Concurrency:  concurrency,
		}
		
		if err != nil {
			result.ErrMsg = err.Error()
			result.HTTPStatus = 500
		}
		
		select {
		case results <- result:
		default:
			log.Printf("Warning: Results channel full, dropping result")
		}
	}
}

func collectResults(results <-chan RequestResult, parquetWriter *storage.ParquetWriter) {
	for result := range results {
		if err := parquetWriter.WriteResult(result); err != nil {
			log.Printf("Error writing result: %v", err)
		}
	}
}

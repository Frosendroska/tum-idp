package main

import (
	"time"
)

// RequestResult represents the result of a single GET request
type RequestResult struct {
	Timestamp     time.Time `parquet:"name=ts, type=INT64, convertedtype=TIMESTAMP_MILLIS"`
	ThreadID      int       `parquet:"name=thread_id, type=INT32"`
	ConnID        int       `parquet:"name=conn_id, type=INT32"`
	ObjectKey     string    `parquet:"name=object_key, type=BYTE_ARRAY, convertedtype=UTF8"`
	RangeStart    int64     `parquet:"name=range_start, type=INT64"`
	RangeLen      int64     `parquet:"name=range_len, type=INT64"`
	Bytes         int64     `parquet:"name=bytes, type=INT64"`
	LatencyMs     float64   `parquet:"name=latency_ms, type=DOUBLE"`
	HTTPStatus    int       `parquet:"name=http_status, type=INT32"`
	RetryCount    int       `parquet:"name=retry_count, type=INT32"`
	ErrMsg        string    `parquet:"name=err_msg, type=BYTE_ARRAY, convertedtype=UTF8"`
	InstanceType  string    `parquet:"name=instance_type, type=BYTE_ARRAY, convertedtype=UTF8"`
	Concurrency   int       `parquet:"name=concurrency, type=INT32"`
	RTTUs         int64     `parquet:"name=rtt_us, type=INT64"`
	TCPRetx       int       `parquet:"name=tcp_retx, type=INT32"`
	LinkUtilPct   float64   `parquet:"name=link_util_pct, type=DOUBLE"`
}

// Config holds the benchmark configuration
type Config struct {
	URL              string
	InstanceType     string
	RangeSize        int64
	SteadyStateHours int
	BucketName       string
	ObjectKey        string
	ObjectSize       int64
	WarmupMinutes    int
	RampStepMinutes  int
	RampStepSize     int
	MaxConcurrency   int
}

// Metrics holds aggregated metrics
type Metrics struct {
	ThroughputMbps float64
	LatencyP50     float64
	LatencyP90     float64
	LatencyP95     float64
	LatencyP99     float64
	QPS            float64
	ErrorRate      float64
	Concurrency    int
	Timestamp      time.Time
}

// NetworkStats holds network interface statistics
type NetworkStats struct {
	BytesReceived    int64
	BytesSent        int64
	PacketsReceived  int64
	PacketsSent      int64
	Retransmits      int64
	Timestamp        time.Time
}

// SystemStats holds system-level statistics
type SystemStats struct {
	CPUUtilization float64
	IRQRate        float64
	MemoryUsage    float64
	Timestamp      time.Time
} 
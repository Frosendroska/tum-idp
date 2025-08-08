package storage

import (
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// PrometheusExporter handles Prometheus metrics collection and serving
type PrometheusExporter struct {
	// Metrics
	throughputGauge    *prometheus.GaugeVec
	latencyHistogram   *prometheus.HistogramVec
	qpsCounter         *prometheus.CounterVec
	errorCounter       *prometheus.CounterVec
	concurrencyGauge   *prometheus.GaugeVec
	networkGauge       *prometheus.GaugeVec
	cpuGauge           *prometheus.GaugeVec

	// Internal state
	mutex     sync.RWMutex
	lastQPS   float64
	lastError float64
}

// NewPrometheusExporter creates a new Prometheus exporter
func NewPrometheusExporter() *PrometheusExporter {
	exporter := &PrometheusExporter{
		throughputGauge: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "r2_bench_throughput_mbps",
				Help: "Current throughput in Mbps",
			},
			[]string{"instance_type", "concurrency"},
		),
		latencyHistogram: prometheus.NewHistogramVec(
			prometheus.HistogramOpts{
				Name:    "r2_bench_latency_ms",
				Help:    "Request latency in milliseconds",
				Buckets: prometheus.ExponentialBuckets(1, 2, 20), // 1ms to ~1s
			},
			[]string{"instance_type", "concurrency"},
		),
		qpsCounter: prometheus.NewCounterVec(
			prometheus.CounterOpts{
				Name: "r2_bench_requests_total",
				Help: "Total number of requests",
			},
			[]string{"instance_type", "concurrency", "status"},
		),
		errorCounter: prometheus.NewCounterVec(
			prometheus.CounterOpts{
				Name: "r2_bench_errors_total",
				Help: "Total number of errors",
			},
			[]string{"instance_type", "concurrency", "error_type"},
		),
		concurrencyGauge: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "r2_bench_concurrency",
				Help: "Current concurrency level",
			},
			[]string{"instance_type"},
		),
		networkGauge: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "r2_bench_network_utilization",
				Help: "Network utilization percentage",
			},
			[]string{"instance_type", "metric"},
		),
		cpuGauge: prometheus.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "r2_bench_cpu_utilization",
				Help: "CPU utilization percentage",
			},
			[]string{"instance_type"},
		),
	}

	// Register metrics
	prometheus.MustRegister(
		exporter.throughputGauge,
		exporter.latencyHistogram,
		exporter.qpsCounter,
		exporter.errorCounter,
		exporter.concurrencyGauge,
		exporter.networkGauge,
		exporter.cpuGauge,
	)

	return exporter
}

// StartServer starts the Prometheus HTTP server
func (pe *PrometheusExporter) StartServer(addr string) error {
	http.Handle("/metrics", promhttp.Handler())
	return http.ListenAndServe(addr, nil)
}

// RecordRequest records a single request result
func (pe *PrometheusExporter) RecordRequest(instanceType string, concurrency int, latencyMs float64, status int, errMsg string) {
	pe.mutex.Lock()
	defer pe.mutex.Unlock()

	// Record latency
	pe.latencyHistogram.WithLabelValues(instanceType, fmt.Sprintf("%d", concurrency)).Observe(latencyMs)

	// Record request count
	statusStr := fmt.Sprintf("%d", status)
	pe.qpsCounter.WithLabelValues(instanceType, fmt.Sprintf("%d", concurrency), statusStr).Inc()

	// Record errors
	if errMsg != "" {
		pe.errorCounter.WithLabelValues(instanceType, fmt.Sprintf("%d", concurrency), "request_error").Inc()
	} else if status >= 400 {
		pe.errorCounter.WithLabelValues(instanceType, fmt.Sprintf("%d", concurrency), "http_error").Inc()
	}
}

// UpdateThroughput updates the throughput metric
func (pe *PrometheusExporter) UpdateThroughput(instanceType string, concurrency int, throughputMbps float64) {
	pe.throughputGauge.WithLabelValues(instanceType, fmt.Sprintf("%d", concurrency)).Set(throughputMbps)
}

// UpdateConcurrency updates the concurrency metric
func (pe *PrometheusExporter) UpdateConcurrency(instanceType string, concurrency int) {
	pe.concurrencyGauge.WithLabelValues(instanceType).Set(float64(concurrency))
}

// UpdateNetworkStats updates network-related metrics
func (pe *PrometheusExporter) UpdateNetworkStats(instanceType string, linkUtilPct, tcpRetx float64) {
	pe.networkGauge.WithLabelValues(instanceType, "link_utilization").Set(linkUtilPct)
	pe.networkGauge.WithLabelValues(instanceType, "tcp_retransmits").Set(tcpRetx)
}

// UpdateCPUStats updates CPU-related metrics
func (pe *PrometheusExporter) UpdateCPUStats(instanceType string, cpuUtilization float64) {
	pe.cpuGauge.WithLabelValues(instanceType).Set(cpuUtilization)
}

// GetMetrics returns current metric values for monitoring
func (pe *PrometheusExporter) GetMetrics() map[string]float64 {
	pe.mutex.RLock()
	defer pe.mutex.RUnlock()

	return map[string]float64{
		"last_qps":   pe.lastQPS,
		"last_error": pe.lastError,
	}
}

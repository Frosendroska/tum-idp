package instances

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
	"bufio"
)

// EC2Monitor handles EC2 instance monitoring and system statistics
type EC2Monitor struct {
	instanceType string
	lastStats    *SystemStats
}

// SystemStats holds system-level statistics
type SystemStats struct {
	CPUUtilization float64
	IRQRate        float64
	MemoryUsage    float64
	NetworkStats   *NetworkStats
	Timestamp      time.Time
}

// NetworkStats holds network interface statistics
type NetworkStats struct {
	BytesReceived    int64
	BytesSent        int64
	PacketsReceived  int64
	PacketsSent      int64
	Retransmits      int64
	LinkUtilPct      float64
}

// NewEC2Monitor creates a new EC2 monitor
func NewEC2Monitor() (*EC2Monitor, error) {
	instanceType := getInstanceType()
	
	return &EC2Monitor{
		instanceType: instanceType,
		lastStats:    &SystemStats{},
	}, nil
}

// GetSystemStats collects current system statistics
func (em *EC2Monitor) GetSystemStats() (*SystemStats, error) {
	stats := &SystemStats{
		Timestamp: time.Now(),
	}

	// Get CPU utilization
	cpuUtil, err := em.getCPUUtilization()
	if err != nil {
		return nil, fmt.Errorf("failed to get CPU utilization: %w", err)
	}
	stats.CPUUtilization = cpuUtil

	// Get IRQ rate
	irqRate, err := em.getIRQRate()
	if err != nil {
		return nil, fmt.Errorf("failed to get IRQ rate: %w", err)
	}
	stats.IRQRate = irqRate

	// Get memory usage
	memUsage, err := em.getMemoryUsage()
	if err != nil {
		return nil, fmt.Errorf("failed to get memory usage: %w", err)
	}
	stats.MemoryUsage = memUsage

	// Get network statistics
	netStats, err := em.getNetworkStats()
	if err != nil {
		return nil, fmt.Errorf("failed to get network stats: %w", err)
	}
	stats.NetworkStats = netStats

	em.lastStats = stats
	return stats, nil
}

// getCPUUtilization reads CPU utilization from /proc/stat
func (em *EC2Monitor) getCPUUtilization() (float64, error) {
	file, err := os.Open("/proc/stat")
	if err != nil {
		return 0, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	if scanner.Scan() {
		line := scanner.Text()
		fields := strings.Fields(line)
		if len(fields) >= 5 && fields[0] == "cpu" {
			// Parse CPU times
			user, _ := strconv.ParseInt(fields[1], 10, 64)
			nice, _ := strconv.ParseInt(fields[2], 10, 64)
			system, _ := strconv.ParseInt(fields[3], 10, 64)
			idle, _ := strconv.ParseInt(fields[4], 10, 64)
			
			total := user + nice + system + idle
			used := user + nice + system
			
			if total > 0 {
				return float64(used) / float64(total) * 100, nil
			}
		}
	}
	
	return 0, nil
}

// getIRQRate reads IRQ rate from /proc/interrupts
func (em *EC2Monitor) getIRQRate() (float64, error) {
	file, err := os.Open("/proc/interrupts")
	if err != nil {
		return 0, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	totalIRQs := 0
	lineCount := 0
	
	for scanner.Scan() && lineCount < 10 {
		line := scanner.Text()
		fields := strings.Fields(line)
		if len(fields) > 0 {
			// Count IRQs (first field is usually the IRQ number)
			if _, err := strconv.Atoi(fields[0]); err == nil {
				totalIRQs++
			}
		}
		lineCount++
	}
	
	// This is a simplified approach - in practice you'd want to track IRQ changes over time
	return float64(totalIRQs), nil
}

// getMemoryUsage reads memory usage from /proc/meminfo
func (em *EC2Monitor) getMemoryUsage() (float64, error) {
	file, err := os.Open("/proc/meminfo")
	if err != nil {
		return 0, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	var total, available int64
	
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "MemTotal:") {
			fields := strings.Fields(line)
			if len(fields) >= 2 {
				total, _ = strconv.ParseInt(fields[1], 10, 64)
			}
		} else if strings.HasPrefix(line, "MemAvailable:") {
			fields := strings.Fields(line)
			if len(fields) >= 2 {
				available, _ = strconv.ParseInt(fields[1], 10, 64)
			}
		}
	}
	
	if total > 0 {
		used := total - available
		return float64(used) / float64(total) * 100, nil
	}
	
	return 0, nil
}

// getNetworkStats reads network statistics from /proc/net/dev
func (em *EC2Monitor) getNetworkStats() (*NetworkStats, error) {
	file, err := os.Open("/proc/net/dev")
	if err != nil {
		return nil, err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	stats := &NetworkStats{}
	
	// Skip header lines
	scanner.Scan()
	scanner.Scan()
	
	for scanner.Scan() {
		line := scanner.Text()
		fields := strings.Fields(line)
		if len(fields) >= 17 {
			// Look for the primary network interface (usually eth0 or ens5)
			if strings.Contains(fields[0], "eth0") || strings.Contains(fields[0], "ens5") {
				stats.BytesReceived, _ = strconv.ParseInt(fields[1], 10, 64)
				stats.PacketsReceived, _ = strconv.ParseInt(fields[2], 10, 64)
				stats.BytesSent, _ = strconv.ParseInt(fields[9], 10, 64)
				stats.PacketsSent, _ = strconv.ParseInt(fields[10], 10, 64)
				break
			}
		}
	}
	
	// Calculate link utilization (simplified)
	// In practice, you'd want to track this over time to get actual utilization
	stats.LinkUtilPct = 0.0
	
	return stats, nil
}

// getInstanceType retrieves the EC2 instance type
func getInstanceType() string {
	// Try to read from EC2 metadata service
	// This is a simplified version - in practice you'd want to handle timeouts and errors
	if data, err := os.ReadFile("/sys/hypervisor/uuid"); err == nil {
		if strings.HasPrefix(string(data), "ec2") {
			// This indicates we're on EC2, but doesn't give us the instance type
			// In a real implementation, you'd query the EC2 metadata service
			return "ec2-instance"
		}
	}
	
	// Fallback to environment variable or default
	if instanceType := os.Getenv("EC2_INSTANCE_TYPE"); instanceType != "" {
		return instanceType
	}
	
	return "unknown"
}

// GetInstanceType returns the detected instance type
func (em *EC2Monitor) GetInstanceType() string {
	return em.instanceType
}

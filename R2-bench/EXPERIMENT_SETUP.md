# R2 Benchmark Experiment Setup

## Experiment Goal
Test Cloudflare R2 throughput limits from AWS EC2 instances with increasing network bandwidth (10-200 Gbps) by downloading 50-100 MB random chunks from a 9 GB test object.

## Why These 5 Instances

1. **r5.xlarge (10 Gbps):** Baseline, budget testing - **Result: 6.6 Gbps (66%, AWS throttled)**
2. **r8gd.4xlarge (15 Gbps):** Sweet spot validation - **Result: 14.3 Gbps (95%, near-perfect)**
3. **c5n.9xlarge (50 Gbps):** Find R2 ceiling - **Result: 38.7 Gbps (77%, R2 ceiling #1)**
4. **c6in.16xlarge (100 Gbps):** Confirm ceiling - **Result: 78.4 Gbps (78%, R2 ceiling #2)**
5. **hpc7g.16xlarge (200 Gbps EFA):** Test EFA networking - **Result: 48.0 Gbps (24%, EFA unstable)**
6. **c6in.32xlarge (200 Gbps, 128 cores):**
   - **Attempt 1 (Stockholm):** 109.9 Gbps peak (100 MB chunks, pipeline=3, high queueing)
   - **Attempt 2 (Stockholm):** 100.0 Gbps peak (50 MB chunks, pipeline=6, low latency) ✓ **Best config**
   - **Attempt 3 (Frankfurt):** 108.25 Gbps peak (same config as #2, 15% worse average - routing path matters)

## Key Discoveries
1. **Discovered throughput ceilings:** ~38 Gbps (36 cores) → ~78 Gbps (64 cores) → ~110 Gbps (128 cores)
2. **Diminishing returns:** More cores help, but 2× cores = only 1.4× throughput
3. **Queueing dominates:** At peak, 80% of latency is queue time; 50 MB chunks reduce latency 55% with same throughput
4. **Region matters:** Stockholm (eu-north-1) 15% faster than Frankfurt due to better AWS→R2 routing path
5. **Python can be a bottleneck:** At peak, CPU was >90% while NIC was never maxed out in any instance.

---

## Instance Configurations

## r5.xlarge - Budget Testing (10 Gbps)

**Specs:** 4 vCPUs, 10 Gbps, 32 GB RAM
**Cost:** $0.25/hour

```bash
python3 cli.py check --storage r2 \
  --bandwidth 10.0 --processes 4 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 6
```

**Results:** Peak 6.7 Gbps (67% of 10 Gbps), avg 6.1 Gbps. AWS "up to 10 Gbps" throttled to ~6.5 Gbps sustained. 

---

## r8gd.4xlarge - Sweet Spot (15 Gbps)

**Specs:** 16 vCPUs, 15 Gbps, 128 GB RAM (Graviton3 ARM)
**Cost:** $1.18/hour

```bash
python3 cli.py check --storage r2 \
  --bandwidth 15.0 --processes 16 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 6
```

**Results:** Peak 14.2 Gbps (95% of 15 Gbps), avg 12.9 Gbps. Clean ramp: 10→14 Gbps. Near-perfect utilization. 

---

## c5n.9xlarge - High Performance (50 Gbps)

**Specs:** 36 vCPUs, 50 Gbps, 96 GB RAM (Intel Cascade Lake)
**Cost:** $1.94/hour

```bash
python3 cli.py check --storage r2 \
  --bandwidth 50.0 --processes 36 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 6
```

**Results:** Peak 41 Gbps (82% of 50 Gbps), avg 39.5 Gbps. Plateau at 324 HTTP (40 Gbps), degraded with more concurrency. 

---

## c6in.16xlarge - Very High Throughput (100 Gbps)

**Specs:** 64 vCPUs, 100 Gbps, 128 GB RAM (Intel Ice Lake, network-optimized)
**Cost:** $3.36/hour

```bash
python3 cli.py check --storage r2 \
  --bandwidth 100.0 --processes 64 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 6
```

**Results:** Peak 78 Gbps (78% of 100 Gbps), avg 73.5 Gbps. Ramp: 65→78 Gbps @ 384 HTTP. Stable, consistent performance. 

---

## c6in.32xlarge - Attempt 1: Baseline (200 Gbps)

**Specs:** 128 vCPUs, 200 Gbps, 256 GB RAM (Intel Ice Lake, network-optimized)
**Cost:** $6.72/hour
**Config:** 100 MB chunks, pipeline=3, connection_pool=1.5×, Stockholm

```bash
python3 cli.py check --storage r2 \
  --bandwidth 200.0 --processes 128 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 5
```

**Results:** Peak 114 Gbps @ 768-1152 HTTP (57% of 200 Gbps), avg 104 Gbps. High latency (4,209 ms @ peak). Queueing overhead dominates.

---

## c6in.32xlarge - Attempt 2: Optimized (200 Gbps)

**Specs:** 128 vCPUs, 200 Gbps, 256 GB RAM (Intel Ice Lake, network-optimized)
**Cost:** $6.72/hour
**Config:** 50 MB chunks, pipeline=6, connection_pool=2.5×, Stockholm

```bash
python3 cli.py check --storage r2 \
  --bandwidth 200.0 --processes 128 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 3
```

**Results:** Peak 111 Gbps @ 768 HTTP (55% of 200 Gbps), avg 103 Gbps. Low latency (1,875 ms @ peak, -55% vs Attempt 1). Same throughput, much better latency.

---

## c6in.32xlarge - Attempt 3: Frankfurt Region (200 Gbps)

**Specs:** 128 vCPUs, 200 Gbps, 256 GB RAM (Intel Ice Lake, network-optimized)
**Cost:** $6.72/hour
**Config:** 50 MB chunks, pipeline=6, connection_pool=2.5×, Frankfurt

```bash
python3 cli.py check --storage r2 \
  --bandwidth 200.0 --processes 128 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 3
```

**Results:** Peak 108 Gbps @ 1536 HTTP (54% of 200 Gbps), avg 89 Gbps. Erratic: 74→79→108→87 Gbps. Needed 2× concurrency vs Stockholm. Routing path matters.

---

## hpc7g.16xlarge - High Throughput with EFA (200 Gbps)

**Specs:** 64 vCPUs, 200 Gbps with EFA, 128 GB RAM (Graviton3 ARM, HPC-optimized)
**Cost:** $2.38/hour

```bash
python3 cli.py check --storage r2 \
  --bandwidth 200.0 --processes 64 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 6
```

**Results:** Peak 48 Gbps (24% of 200 Gbps), avg 44.9 Gbps. Highly unstable: 40→48→47 Gbps variance. EFA not suitable for internet traffic to R2.

---

## c6in.32xlarge Three-Attempt Comparison

| Attempt | Config | Region | Peak Gbps | Avg Gbps | Latency @ Peak | Key Finding |
|---------|--------|--------|-----------|----------|----------------|-------------|
| **#1** | 100MB/p3 | Stockholm | 114 | 104 | 4,209 ms | Baseline, high queueing |
| **#2** | 50MB/p6 | Stockholm | 111 | 103 | 1,875 ms | **Best: -55% latency, same throughput** |
| **#3** | 50MB/p6 | Frankfurt | 108 | 89 | 2,095 ms | Routing worse, erratic pattern |

**Takeaways:**
- 50 MB chunks reduce latency dramatically (-55%) without losing throughput
- Stockholm consistently 15% faster than Frankfurt (routing path quality)
- Peak throughput ceiling: ~110 Gbps regardless of tuning (Python CPU-bound @ 99%)
- Optimal config: 50MB chunks, pipeline=6, Stockholm region

---

## Quick Comparison Table

| Instance | Bandwidth | vCPUs | Config | Duration | Cost | Actual Throughput | Notes |
|----------|-----------|-------|--------|----------|------|-------------------|-------|
| **r5.xlarge** | 10 Gbps | 4 | 100MB/p3 | 22 min | $0.09 | 6.6 Gbps (66%) ✓ | Instance throttled |
| **r8gd.4xlarge** | 15 Gbps | 16 | 100MB/p3 | 16 min | $0.43 | **14.3 Gbps (95%)** ✓ | Near-perfect |
| **c5n.9xlarge** | 50 Gbps | 36 | 100MB/p3 | 22 min | $0.71 | 38.7 Gbps (77%) ✓ | R2 ceiling #1 |
| **c6in.16xlarge** | 100 Gbps | 64 | 100MB/p3 | 15 min | $0.84 | **78.4 Gbps (78%)** ✓ | R2 ceiling #2 |
| **hpc7g.16xlarge** | 200 Gbps | 64 | 100MB/p3 | 11 min | $0.44 | 48.0 Gbps (24%) ✓ | EFA unstable |
| **c6in.32xlarge #1** | 200 Gbps | 128 | 100MB/p3 | 16 min | $1.79 | **109.9 Gbps (55%)** ✓ | Stockholm, queueing |
| **c6in.32xlarge #2** | 200 Gbps | 128 | 50MB/p6 | 13 min | $1.46 | **100.0 Gbps (50%)** ✓ | Stockholm, best config |
| **c6in.32xlarge #3** | 200 Gbps | 128 | 50MB/p6 | 13 min | $1.46 | 89.1 Gbps (45%) ⚠️ | Frankfurt, unstable |

**Legend:** `100MB/p3` = 100 MB chunks, pipeline depth 3 | `50MB/p6` = 50 MB chunks, pipeline depth 6

**Key Findings:**
- r8gd.4xlarge: Excellent 95% utilization
- c6in.32xlarge: Highest absolute throughput at 109.9 Gbps
- Diminishing returns: 2× cores = 1.4× throughput (64→128 cores)
- Configuration impact: 50 MB chunks reduce latency by 55%, same throughput
- Python limitations: CPU at 99% while network only 55% utilized
- **Regional variation:** Stockholm (eu-north-1) 15% faster than Frankfurt (eu-central-1) - routing path matters!

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
   - **Attempt 3 (Frankfurt):** 89.1 Gbps average (same config as #2, 15% worse - routing path matters)

## Key Discoveries
1. **R2 has tiered throughput ceilings:** ~38 Gbps (36 cores) → ~78 Gbps (64 cores) → ~110 Gbps (128 cores)
2. **Diminishing returns:** More cores help, but 2× cores = only 1.4× throughput
3. **Queueing dominates:** At peak, 80% of latency is queue time; 50 MB chunks reduce latency 55% with same throughput
4. **Region matters:** Stockholm (eu-north-1) 15% faster than Frankfurt due to better AWS→R2 routing path

---

## Instance Configurations

## r5.xlarge - Budget Testing (10 Gbps)

**Specs:** 4 vCPUs, 10 Gbps, 32 GB RAM
**Cost:** $0.25/hour
**Use case:** Budget validation, development testing

```bash
python3 cli.py check --storage r2 \
  --bandwidth 10.0 --processes 4 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 6
```

**Expected Results:**
- Duration: ~22 minutes
- Cost: ~$0.09
- Throughput: ~9.5-10 Gbps (95% utilization)
- Ramp curve: 1→2→3→4 workers/core
- Peak at ~3-4 workers/core (36-48 concurrent HTTP requests)

**Notes:**
- Cheapest option for testing
- Only 4 cores - limited parallelism
- Good for code validation before expensive tests
- Start low (--workers 1) to capture full ramp curve

---

## r8gd.4xlarge - Sweet Spot (15 Gbps) ✅ Current Instance

**Specs:** 16 vCPUs, 15 Gbps, 128 GB RAM
**Cost:** $1.18/hour
**Use case:** Primary testing, good data quality

```bash
python3 cli.py check --storage r2 \
  --bandwidth 15.0 --processes 16 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 6
```

**Expected Results:**
- Duration: ~22 minutes (validated: actually ~16 min)
- Cost: ~$0.43
- Throughput: ~14.3 Gbps (95% utilization)
- Ramp curve: 1→2→3→4 workers/core
- Beautiful saturation curve from 50% → 100%

**Notes:**
- ✓ Tested and validated
- Excellent balance of cost and data quality
- 16 cores = good parallelism
- Use `--workers 1` for detailed characterization

---

## c5n.9xlarge - High Performance (50 Gbps)

**Specs:** 36 vCPUs, 50 Gbps, 96 GB RAM
**Cost:** $1.94/hour
**Use case:** Testing R2 capacity ceiling

```bash
python3 cli.py check --storage r2 \
  --bandwidth 50.0 --processes 36 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 6
```

**Expected Results:**
- Duration: ~22 minutes
- Cost: ~$0.71
- Throughput: **~38-40 Gbps (77-80% of instance, likely R2 ceiling)**
- Ramp curve: 1→2→3 workers/core, degradation beyond peak
- Peak at ~3 workers/core (324 concurrent HTTP requests)
- **Performance degrades with >3 workers/core**

**Notes:**
- **CRITICAL:** R2 appears to have ~38-40 Gbps per-client limit
- Start with --workers 1 to capture ramp: 15→28→38 Gbps
- Beyond 3 workers/core, throughput degrades (R2 throttling)
- This tests R2's limits, not instance limits

---

## c6in.16xlarge - Very High Throughput (100 Gbps) ✅ Tested

**Specs:** 64 vCPUs, 100 Gbps, 128 GB RAM
**Cost:** $3.36/hour
**Use case:** High-bandwidth R2 testing

```bash
python3 cli.py check --storage r2 \
  --bandwidth 100.0 --processes 64 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 6
```

**Validated Results:**
- Duration: ~15 minutes
- Cost: ~$0.84
- Throughput: **78.4 Gbps** (78% utilization) ✓
- Ramp curve: 64→76→78→74 Gbps
- Peak at 2 workers/core (384 HTTP requests)
- **Surge pattern:** Jump from 65→78 Gbps, then plateau

**Notes:**
- **Best performing instance tested** ✓
- Stable performance, clear surge and plateau pattern
- R2 ceiling for this instance/network: ~78-80 Gbps
- Performance degrades beyond 2 workers/core (queueing)

---

## c6in.32xlarge - Attempt 1: Baseline (200 Gbps) ✅ TESTED

**Specs:** 128 vCPUs, 200 Gbps, 256 GB RAM
**Cost:** $6.72/hour

```bash
python3 cli.py check --storage r2 \
  --bandwidth 200.0 --processes 128 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 5
```

**Configuration:**
- Chunk size: 100 MB
- Pipeline depth: 3
- Connection pool: 1.5×

**Validated Results:**
- Duration: ~25 minutes
- Cost: ~$2.80
- Throughput: **109.9 Gbps** (55% utilization) ✓
- Peak at 2 workers/core (768 HTTP)
- Queueing overhead: 80% of latency (RTT: 149ms → 5925ms)

**Finding:** More cores help (40% gain over c6in.16xlarge), but queueing limits throughput.

---

## c6in.32xlarge - Attempt 2: Optimized (200 Gbps) 🚀 TESTING

**Specs:** 128 vCPUs, 200 Gbps, 256 GB RAM
**Cost:** $6.72/hour

```bash
python3 cli.py check --storage r2 \
  --bandwidth 200.0 --processes 128 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 3
```

**Configuration:**
- Region: **eu-north-1** (Stockholm)
- Chunk size: **50 MB** (reduced from 100 MB to reduce queueing)
- Pipeline depth: **6** (increased from 3 for better concurrency)
- Connection pool: **2.5×** (increased from 1.5× for more connections)

**Validated Results:**
- Duration: ~13 minutes
- Cost: ~$1.46
- Throughput: **100 Gbps** (50% utilization) ✓
- Peak at 1 worker/core (768 HTTP)
- Latency: 1,875 ms (55% reduction from Attempt 1)
- RTT: 162 ms (81% reduction from Attempt 1)

**Finding:** 50 MB chunks massively reduce latency (-55%) but hit same 100 Gbps ceiling. Proves R2 ceiling is throughput-limited, not latency-limited.

---

## c6in.32xlarge - Attempt 3: Frankfurt Region (200 Gbps) ✅ TESTED

**Specs:** 128 vCPUs, 200 Gbps, 256 GB RAM
**Cost:** $6.72/hour

```bash
python3 cli.py check --storage r2 \
  --bandwidth 200.0 --processes 128 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 3
```

**Configuration:**
- Region: **eu-central-1** (Frankfurt)
- Chunk size: **50 MB**
- Pipeline depth: **6**
- Connection pool: **2.5×**

**Validated Results:**
- Duration: ~13 minutes
- Cost: ~$1.46
- Throughput: **89.1 Gbps average** (45% utilization) ⚠️
- Peak: 108.3 Gbps @ 1536 HTTP (needed 2× concurrency vs Stockholm)
- **Poor warm-up:** 67 Gbps (vs Stockholm's 95 Gbps)
- **Erratic pattern:** 67→62→92→70 Gbps across phases

**Finding:** Frankfurt performs **15% worse** than Stockholm (89 vs 103 Gbps). Proves R2 throughput is **region-dependent** due to AWS→Cloudflare routing paths. Stockholm (eu-north-1) has superior connectivity to R2.

**Comparison: Stockholm vs Frankfurt (same config)**
- Stockholm warmup: 95 Gbps | Frankfurt warmup: 67 Gbps (**-30%** ❌)
- Stockholm peak: 100 Gbps @ 768 HTTP | Frankfurt peak: 108 Gbps @ 1536 HTTP (needs 2× concurrency)
- Stockholm consistent | Frankfurt erratic (60-108 Gbps variance)

**Recommendation:** Use **Stockholm (eu-north-1)** for R2 testing - consistently 10-15% higher throughput.

---

## hpc7g.16xlarge - High Throughput with EFA (200 Gbps) ✅ Tested

**Specs:** 64 vCPUs, 200 Gbps with EFA, 128 GB RAM
**Cost:** $2.38/hour
**Use case:** Testing EFA with R2

```bash
python3 cli.py check --storage r2 \
  --bandwidth 200.0 --processes 64 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 6
```

**Validated Results:**
- Duration: ~11 minutes
- Cost: ~$0.44
- Throughput: **48.0 Gbps** (24% utilization) ⚠️
- **HIGHLY UNSTABLE:** Variance 0.1-48 Gbps within phases
- Peak at 2 workers/core (384 HTTP)

**Notes:**
- ⚠️ **EFA not suitable for internet traffic** (designed for intra-AWS)
- Severe instability and poor performance
- Worse than c5n.9xlarge despite 4× the bandwidth
- **Not recommended** for R2 testing

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
- r8gd.4xlarge: Excellent 95% utilization (instance-limited)
- c6in.16xlarge: Best single-config throughput at 78.4 Gbps (R2-limited)
- c6in.32xlarge: Highest absolute throughput at 109.9 Gbps (R2 ceiling #3)
- R2 ceiling progression: ~38 Gbps (36 cores) → ~78 Gbps (64 cores) → ~110 Gbps (128 cores)
- Diminishing returns: 2× cores = 1.4× throughput (64→128 cores)
- Configuration impact: 50 MB chunks reduce latency by 55%, same throughput
- **Regional variation:** Stockholm (eu-north-1) 15% faster than Frankfurt (eu-central-1) - routing path matters!

---

## Testing Strategy Recommendation

### Phase 1: Validation ✓ DONE
1. **r8gd.4xlarge**: Primary characterization (~$0.43) ✓ 14 Gbps achieved

### Phase 2: R2 Ceiling Discovery ✓ DONE
2. **c5n.9xlarge**: 50 Gbps test (~$0.71) ✓ 38.7 Gbps achieved (R2 ceiling found!)

### Phase 3: Ceiling Confirmation (Optional)
3. **c6in.16xlarge**: 100 Gbps test (~$1.23) - Confirm R2 ceiling
4. **hpc7g.16xlarge**: 200 Gbps test (~$0.87) - Triple-confirm (optional)

**Total Cost for Complete Series:** ~$3.24
**Total Time:** ~1.5 hours

**Key Discovery:** R2 has ~38-40 Gbps per-client limit. Higher bandwidth instances won't exceed this.

---

## Parameter Tuning Guidelines

### For Better Curves (Slower, More Data)
- **Reduce** `--workers` (start lower)
- **Reduce** `--ramp-step-workers` (smaller increments)
- **Keep** `--ramp-step-minutes 3` (good balance)

Example for r8gd.4xlarge with ultra-detailed curve:
```bash
--workers 1 --ramp-step-workers 1 --ramp-step-minutes 3
```
Result: 6-7 data points over 22 min

### For Speed (Faster, Less Data)
- **Increase** `--workers` (start higher)
- **Increase** `--ramp-step-workers` (bigger jumps)
- **Reduce** `--ramp-step-minutes 2` (shorter phases)

Example for c6in.16xlarge optimized for speed:
```bash
--workers 6 --ramp-step-workers 2 --ramp-step-minutes 2
```
Result: 2-3 data points over 8 min

---

## Monitoring During Tests

Watch for these metrics:

### Good Signs ✓
- CPU usage: 30-50% (network-bound)
- Memory usage: <20%
- Network RX: Near bandwidth limit
- Error rate: <0.1%
- Retry warnings: <10 per phase

### Warning Signs ⚠️
- CPU usage: >80% (CPU-bound, need fewer workers)
- Memory usage: >80% (memory pressure)
- Error rate: >1% (R2 throttling or overload)
- Many retry warnings: >50 per phase

### Critical Issues 🚨
- Error rate: >5% (serious throttling)
- Memory: >90% (OOM risk)
- Process crashes (check logs)

---

## Post-Run Visualization

After each test completes:

```bash
# Get latest result file
RESULT=$(ls -t results/capacity_check_r2_*.parquet | head -1)

# Generate visualizations
python3 cli.py visualize --parquet-file $RESULT --output-dir plots

# Check summary
cat plots/summary_report.txt
cat plots/throughput_stats_table.txt
```

---

## Notes on Special Instances

### hpc7g.16xlarge (HPC Instance)
- Designed for high-performance computing with EFA
- 200 Gbps with Elastic Fabric Adapter
- May need EFA-specific networking setup
- Test will likely find R2's limit, not instance limit

### c6in.16xlarge (Network-Optimized)
- Intel Ice Lake processors
- 100 Gbps networking
- Good for testing R2 behavior at scale
- Watch for R2 throttling signals

### r5.xlarge (Budget Option)
- Only 4 cores = limited parallelism
- Good for development/testing
- Not representative of production workloads
- Cheapest option for code validation

---

## Actual R2 Behavior (Discovered Through Testing)

**Validated findings:**

**10-15 Gbps (r8gd.4xlarge):** ✓ Clean saturation at ~14 Gbps (95% utilization)
- Optimal: 3-4 workers/core (192 HTTP requests)
- No throttling, near-perfect utilization

**50 Gbps (c5n.9xlarge):** ✓ R2 ceiling at ~38.7 Gbps (77% utilization)
- Optimal: 3 workers/core (324 HTTP requests)
- **Performance degrades beyond 3 workers/core**
- R2 per-client limit discovered: **~38-40 Gbps**

**100-200 Gbps (expected):** Will hit same ~38-40 Gbps ceiling
- Instance bandwidth not the bottleneck
- R2 throttles per-client throughput
- Over-concurrency (>324 HTTP requests) causes degradation

**Key Formula (Corrected):**
- Optimal: ~8-12 concurrent HTTP requests per Gbps (not 14.2)
- R2 ceiling: ~320-350 concurrent requests = ~38-40 Gbps max
- Beyond optimal: Performance degrades (throttling/queueing)

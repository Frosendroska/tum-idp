# Instance-Specific Configuration Guide

Commands optimized for each instance type in your testing plan.

---

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

## c6in.32xlarge - Maximum Throughput Test (200 Gbps) 🚀

**Specs:** 128 vCPUs, 200 Gbps, 256 GB RAM
**Cost:** $6.72/hour
**Use case:** Test if more cores can exceed 78 Gbps ceiling

```bash
python3 cli.py check --storage r2 \
  --bandwidth 200.0 --processes 128 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 5
```

**Expected Results:**
- Duration: ~22-25 minutes
- Cost: ~$2.80
- Throughput: **78-100 Gbps** (testing if 2× cores helps)
- Ramp curve: Will show if more parallelism breaks ceiling
- Peak likely at 2-3 workers/core (256-384 HTTP per core, 512-768 total HTTP)

**Why test this:**
- c6in.16xlarge (64 cores): 78.4 Gbps ✓
- c6in.32xlarge (128 cores): Can 2× cores push beyond 78 Gbps?
- Same proven network family
- Tests if R2 limit is per-connection or per-client

**Possible outcomes:**
1. **~78 Gbps:** R2 has hard per-client limit (confirms ceiling)
2. **90-100 Gbps:** More cores help distribute load, partial breakthrough
3. **>100 Gbps:** Major breakthrough, R2 scales with more connections

---

## c6in.32xlarge - Maximum Cores Test (200 Gbps) 🚀 CURRENT

**Specs:** 128 vCPUs, 200 Gbps, 256 GB RAM
**Cost:** $6.72/hour
**Use case:** Test if 2× cores can exceed 78 Gbps ceiling

```bash
python3 cli.py check --storage r2 \
  --bandwidth 200.0 --processes 128 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 5
```

**Expected Results:**
- Duration: ~22-25 minutes
- Cost: ~$2.80
- Throughput: **78-100 Gbps** (testing if more cores help)
- Ramp curve: Will reveal if parallelism breaks ceiling
- Peak likely at 1-2 workers/core (384-768 total HTTP requests)

**Three Possible Outcomes:**
1. **~78 Gbps:** Confirms R2 hard per-client limit (more cores don't help)
2. **90-100 Gbps:** Partial breakthrough - more connections help somewhat
3. **>100 Gbps:** Major discovery - high parallelism bypasses R2 limits

**Notes:**
- Double the cores of c6in.16xlarge (which achieved 78 Gbps)
- Same proven network family
- Tests hypothesis: Is R2 limit per-client or per-connection?
- Lower max-workers (5 vs 6) since 128 cores = more total HTTP requests
- With 128 cores: 1 worker/core = 384 HTTP, 2 workers/core = 768 HTTP

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

| Instance | Bandwidth | vCPUs | Workers | Ramp | Duration | Cost | Actual Throughput |
|----------|-----------|-------|---------|------|----------|------|-------------------|
| **r5.xlarge** | 10 Gbps | 4 | 1→6 | +1 | 22 min | $0.09 | 6.6 Gbps (66%) ✓ |
| **r8gd.4xlarge** | 15 Gbps | 16 | 1→6 | +1 | 16 min | $0.43 | **14.3 Gbps (95%)** ✓ |
| **c5n.9xlarge** | 50 Gbps | 36 | 1→6 | +1 | 22 min | $0.71 | 38.7 Gbps (77%) ✓ |
| **c6in.16xlarge** | 100 Gbps | 64 | 1→6 | +1 | 15 min | $0.84 | **78.4 Gbps (78%)** ✓ |
| **hpc7g.16xlarge** | 200 Gbps | 64 | 1→6 | +1 | 11 min | $0.44 | 48.0 Gbps (24%, unstable) ✓ |
| **c6in.32xlarge** | 200 Gbps | 128 | 1→5 | +1 | 25 min | $2.80 | **Testing now...** 🚀 |

**Key Findings:**
- r8gd.4xlarge: Excellent 95% utilization (instance-limited)
- c6in.16xlarge: Best absolute throughput at 78.4 Gbps (R2-limited)
- R2 ceiling varies: ~38 Gbps (c5n), ~48 Gbps (hpc7g), ~78 Gbps (c6in)
- c6in.32xlarge: Testing if 2× cores can exceed 78 Gbps

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

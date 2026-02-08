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

## c6in.16xlarge - Very High Throughput (100 Gbps)

**Specs:** 64 vCPUs, 100 Gbps, 128 GB RAM
**Cost:** $3.36/hour
**Use case:** Confirm R2 capacity ceiling

```bash
python3 cli.py check --storage r2 \
  --bandwidth 100.0 --processes 64 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 6
```

**Expected Results:**
- Duration: ~22 minutes
- Cost: ~$1.23
- Throughput: **~38-40 Gbps (same ceiling as c5n.9xlarge)**
- Ramp curve: 1→2→3 workers/core
- Peak at ~2-3 workers/core
- **Will NOT reach 100 Gbps - R2 limit is ~40 Gbps**

**Notes:**
- **Expensive but necessary**: $3.36/hour to confirm R2 ceiling
- Start with --workers 1 to capture full curve
- Expected to hit same ~40 Gbps ceiling as c5n.9xlarge
- Proves R2 per-client limit, not instance limit

---

## hpc7g.16xlarge - Extreme Throughput (200 Gbps)

**Specs:** 64 vCPUs, 200 Gbps with EFA, 128 GB RAM
**Cost:** $2.38/hour
**Use case:** Final confirmation of R2 ceiling

```bash
python3 cli.py check --storage r2 \
  --bandwidth 200.0 --processes 64 \
  --workers 1 --ramp-step-workers 1 --ramp-step-minutes 3 --max-workers 6
```

**Expected Results:**
- Duration: ~22 minutes
- Cost: ~$0.87
- Throughput: **~38-40 Gbps (same R2 ceiling)**
- Ramp curve: 1→2→3 workers/core
- Peak at ~2-3 workers/core
- **Will NOT exceed 40 Gbps - R2 per-client limit**

**Notes:**
- **Optional test** - c6in.16xlarge likely sufficient to confirm ceiling
- Same ~40 Gbps limit expected (R2 throttling, not instance)
- EFA provides ultra-low latency but won't bypass R2 limits
- Purpose: Triple-confirm R2's per-client throughput ceiling
- Consider skipping if budget-constrained

---

## Quick Comparison Table

| Instance | Bandwidth | vCPUs | Workers | Ramp | Duration | Cost | Expected Throughput |
|----------|-----------|-------|---------|------|----------|------|---------------------|
| **r5.xlarge** | 10 Gbps | 4 | 1→6 | +1 | 22 min | $0.09 | ~10 Gbps (95%) |
| **r8gd.4xlarge** | 15 Gbps | 16 | 1→6 | +1 | 22 min | $0.43 | ~14 Gbps (95%) ✓ |
| **c5n.9xlarge** | 50 Gbps | 36 | 1→6 | +1 | 22 min | $0.71 | **~38 Gbps (R2 limit)** ✓ |
| **c6in.16xlarge** | 100 Gbps | 64 | 1→6 | +1 | 22 min | $1.23 | **~38 Gbps (R2 limit)** |
| **hpc7g.16xlarge** | 200 Gbps | 64 | 1→6 | +1 | 22 min | $0.87 | **~38 Gbps (R2 limit)** |

**Key Finding:** R2 has a per-client throughput ceiling of ~38-40 Gbps regardless of instance bandwidth.

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

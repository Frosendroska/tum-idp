# R2 Large-Chunk GET Microbenchmark

## TL;DR

> Purpose: Measure R2 GET throughput and latency at scale, with one EC2 client issuing object ranges downloads in parallel, while remaining within R2’s free limits and incurring no egress fees.


## Background & Motivation

Cloudflare R2 exposes an S3‑compatible API, a generous free tier (10 GiB storage, 1 M Class A, 10 M Class B operations) and zero egress fees. Because vendor lock‑in avoidance is predicated on free egress, we must confirm that raw storage performance is not the hidden trade‑off when compared with Amazon S3. A focused micro‑benchmark isolates the storage plane—avoiding Workers, CDN caches, or multi‑client orchestration noise—so any performance gap becomes immediately visible.


## Goals & Non-Goals

Goals:
- Saturate R2’s read‑throughput ceiling from a single host.
- Collect throughput, latency (p50/90/95/99), QPS, and error rates for several hours.
- Stay inside the free tier (storage ≤ 10 GB, GETs ≤ 10 M).
- Demonstrate zero egress cost.


Non-Goals:
- No CDN cache evaluation.
- No Cloudflare Workers or edge compute assessment.
- No sustained write/PUT stress beyond the initial object upload.
- No multi‑region or multi‑client scaling study.


## Constraints

*Cloudflare R2:*
## Cloudflare R2

| Limit             | Free-tier value                              | Rationale                                |
| ----------------- | -------------------------------------------- | ---------------------------------------- |
| Storage           | ≤ 10 GiB-month                               | Keeps us under the hard cap & cost-free  |
| Class B (GET) ops | ≤ 10 M / month                               | Plenty of headroom for a multi-hour test |
| Egress            | $0                                           | Core R2 value proposition                |
| Endpoint          | `https://<ACCOUNT>.r2.cloudflarestorage.com` | Region = auto (EU bucket)                |
| Rate-limit        | `r2.dev` throttles at ~hundreds RPS          | Must use the S3 endpoint above           |

*AWS EC2 (Client):*
- **Instance:** Start with c8gn.large (up to 100 Gbps); scale to c8gn.4xlarge (200 Gbps) and c8gn.8xlarge (300 Gbps) if R2 allows.

- **Network pricing:** Inbound traffic is free; only the instance‑hour is billed (~$0.20 – $0.60 h for mid‑size Graviton 3‑based c8gn).

- **Region:** eu‑central‑1 (Frankfurt) to minimise RTT to the EU‑placed bucket.

## Test Design (Single Workload) ￼ 

- *Object:* 1 immutable object of 1 GiB size. We will read the ranges of this file.
  - _Fits under 10 GB free tier. The file is > 512 MB, so Cloudflare PoPs never store them; every read is served from R2’s regional store. That guarantees you are exercising R2—not Cloudflare’s CDN—throughout all three phases. We can upload an object to the storage only once and then change the range sizes._

- *Request pattern:* Each worker thread GETs the range of the object in a tight loop (connection reuse on; no think time) for the entire run.
  - _Large payloads minimize request count yet still push bandwidth; keep-alive removes TLS handshake overhead and mirrors Amazon S3 best practices for high throughput._

- *Concurrency*: Start at C = 8 connections; ramp upward (+8 every 5 min) until throughput no longer grows or the connection saturates; then hold at the best concurrency for the remainder.
    - *Phases:*
        1.	Warm-up: 5 min at moderate C_{0} = 8 (stabilize connections/paths).
        2.	Ramp: step up C_x - C _{x-1} = 8 every 5 min to find the plateau.
        3.	Steady-state: run at plateau C_{n} for hours to measure the metrics.
    - _Warm-up lets TCP slow-start and TLS session reuse stabilise; ramp finds R2-imposed ceiling; long steady-state captures drift/tail latency. Gradual ramp prevents sudden 429s and mimics AWS “warm-up” guidance.  The threads will round-robin the object keys they fetch. This would avoid creating a single “hot object” bottleneck and instead spread load across multiple keys. There’s no need for complex asynchronous pipelining here because the goal is to maximize throughput per connection for large transfers. We need to verify that the HTTP client library isn’t, for example, defaulting to HTTP/2 and multiplexing all threads over one TCP connection, which could become a bottleneck._

- *Object Storage & Workers:* R2 client with endpoint = `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` in EU. One EC2 in Frankfurt with high bandwidth. 
  - _Avoid the multi-region and multi-client overheads. If NIC counters/CPU/IRQ/Socket errors/No 5 Gb/s flat-line per flow max out before P95 latency jumps, the bottleneck is the EC2._


## Test Plan

- *Phase 0*
- Upload the 1 GiB object (aws s3 cp) once.

- *Phase 1*
- Launch a c8gn.large (100 Gbps‑capable) EC2 in eu‑central‑1.
- Transfer the 100 MB object ranges in a tight loop.
- Warm‑up 1 min at 10 rps.
- Ramp C += 50 every 15 sec; stop when observe TCP-level drops/retransmit with flat-lined throughput -- plateu.
- If we observe TCP-level drops/retransmits that coincide with flat-lined throughput, assume the NIC—not R2—is the bottleneck. 
- Write Parquet logs.
- Record maximum sustainable NIC bandwidth; verify R2 isn’t the immediate bottleneck.

Repeat this phase with different EC2 instances (200 Gbps, then 300 Gbps) to find the one where the R2 is a bottleneck and not the EC2.

- r5.xlarge       --   32 GiB	  4 vCPUs	  EBS only	 Up to 25 Gigabit	 $0.298 hourly
- c5n.9xlarge     --   96 GiB	  36 vCPUs	EBS only	 50 Gigabit	       $1.944 hourly
- c7gn.8xlarge    --   64 GiB   32 vCPUs	EBS only	 100 Gigabit	     $1.9968 hourly
- hpc7g.16xlarge	--   128 GiB	64 vCPUs	EBS only	 200 Gigabit	     $1.6832 hourly

- *Phase 2*
When we find the maximum throughput, we can start an actual test that will find a plateau and microbenchmark the system.

- Take the final instance size selected in Phase 1.
- Transfer the 100 MB object ranges in a tight loop.
- Warm‑up 1 min at 10 rps.
- Ramp C += 10 every 30 sec; stop when observe flat-lined throughput.
- Hold steady‑state at C for ≥ 3 h.
- Continuously scrape Prometheus + write Parquet logs.
- Post‑process: generate throughput timeline, latency CDF, error histogram.


## Implementation details

### Validity check

Responsible for Phase 1 (capacity discovery):

```bash
check 
--url <r2/s3>
--instance <c8gn/c7gn>
```

**Features:**

- Reports peak Mbps and Δ Mbps/step for the specified instance.
- Parquet raw per request.

### Benchmark

The second binary will be responsible for the microbenchmark.

```bash
benchmark 
--url <r2/s3>
--instance <c8gn/c7gn>
--range-size <int>
--steady-state-hours <int>
```

**Features:**

- Prometheus exporter on :9100/metrics.
- Parquet raw per request.


## Metrics Captured

- Throughput (MiB/s, GiB/s) – aggregated per-second.
- Latency – p50/p90/p95/p99 per GET (socket-open → last byte).
- QPS / IOPS – requests per second.
- Error Rates – HTTP 429/5xx, timeouts, retries (with exponential back-off).
- Client Health – NIC Mbps, TCP retransmits, CPU utilisation.

## Tables columns

`ts`,
`thread_id`,
`conn_id`,
`object_key`,
`range_start`,
`range_len`,
`bytes`,
`latency_ms`,
`http_status`,
`retry_count`,
`err_msg`,
`instance_type`,
`concurrency`,
`rtt_us`,
`tcp_retx`,
`link_util_pct`;


## Visualization

*Plots for Grafana and Python script:*

| Plot                | Axis                                    | Insight                                       |
| ------------------- | --------------------------------------- | --------------------------------------------- |
| Throughput timeline | Mbps vs. time (line)                    | Long-term stability & drift                   |
| Latency CDF         | Probability vs. latency_ms (step)       | Tail behaviour (p99/p99.9)                    |
| Error histogram     | Count vs. HTTP code (bar)               | Frequency and class of failures               |
| Concurrency heatmap | C vs. time, colour = Mbps               | Highlights plateau and effect of ramp steps   |
| NIC health          | Mbps & retransmits vs. time (dual-axis) | Correlates network issues with latency spikes |
| CPU vs. IRQs        | %CPU (user+sys) & IRQ/s (line)          | Detects kernel-level bottlenecks              |


## Tooling

*AWS SDK with CRT in Python:* 

*Prometheus and Grafana:* Unified metrics endpoint for both binaries and OS‑level exporters. Used to discover the data during runtime.

*Simple Python visualization:* To visualize the Parquet after the text execution.


## References (key excerpts)

1.	[R2 pricing & free-tier – 10 GB / 10 M GETs / $0 egress](https://developers.cloudflare.com/r2/pricing/?utm_source=chatgpt.com)
2.	[Zero egress billing – R2 product page](https://developers.cloudflare.com/r2/pricing/?utm_source=chatgpt.com)
3.	[r2.dev rate-limit (hundreds RPS)](https://developers.cloudflare.com/r2/platform/limits/?utm_source=chatgpt.com)
4.	[AWS inbound data transfer is free](https://aws.amazon.com/blogs/architecture/overview-of-data-transfer-costs-for-common-architectures/?utm_source=chatgpt.com)
5.	[c7gn instance ≥ 30 Gbps network](https://instances.vantage.sh/?id=c181ce8e55049d7920e67b501e88ceb50202d5dd)
6.	[Parallel connections boost S3 throughput](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance-guidelines.html?utm_source=chatgpt.com)
7.	[AWS CRT multi-thread S3 client enhances throughput](https://aws.amazon.com/blogs/storage/improving-amazon-s3-throughput-for-the-aws-cli-and-boto3-with-the-aws-common-runtime/?utm_source=chatgpt.com)
8.	[S3 gradual scaling / warm-up guidance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html?utm_source=chatgpt.com)
9.	[Auto-scaling services benefit from “ease-in” warm-up](https://aws.amazon.com/blogs/database/handle-traffic-spikes-with-amazon-dynamodb-provisioned-capacity/?utm_source=chatgpt.com)

---
# R2 Large-Chunk GET Microbenchmark

## TL;DR

> Purpose: Measure R2 GET throughput and latency at scale, with one EC2 client issuing large-object downloads in parallel, while remaining within R2’s free limits and incurring no egress fees.


## Background & Motivation

Cloudflare R2 offers an S3-compatible API, a generous free tier (10 GB storage, 1 M Class A, 10 M Class B ops) and no egress fees. Because R2 advertises vendor-lock-in avoidance via free egress, it is important to show that its raw storage performance is not a hidden trade-off compared with AWS S3. A focused micro-benchmark lets us isolate the storage plane without Workers, CDN caches, or multi-client orchestration noise.


## Goals & Non-Goals

Goals:
- Hit R2’s read-throughput ceiling with a single host.
- Collect throughput, latency (p50/90/95/99), QPS, and error rates for several hours.
- Stay inside the free tier (storage ≤ 10 GB, GETs ≤ 10 M).
- Demonstrate zero egress cost.


Non-Goals:
- No CDN cache performance.
- No Cloudflare Workers or compute evaluation.
- No write/PUT stress beyond initial upload.
- No multi-region or multi-client scaling study.


## Constraints

*Cloudflare R2:*
-	Storage: ≤ 10 GB-month (free) ￼
-	Class B GETs: ≤ 10 M/month (free) ￼
-	Egress: $0 across all classes ￼
-	Endpoint: https://<account>.r2.cloudflarestorage.com (S3 API; region=auto) ￼
-	Rate-limit: r2.dev public endpoint throttles at hundreds of RPS—must be avoided ￼

*AWS EC2:*
- Network: choose a “high-network-bandwidth” instance (e.g. c7gn.large up to 30 Gbps; larger sizes reach 200 Gbps) so the NIC does not cap throughput.
- Inbound traffic: free to EC2, so only instance-hour cost ($0.2 – $0.6/h for mid-size Graviton).
- Region: eu-central-1 (Frankfurt) to keep RTT low to an EU-placed bucket.


## Test Design (Single Workload) ￼ 

- *Object:* 9 immutable objects of 1 GiB size.
  - _Fits under 10 GB free tier. Files are > 512 MB, so Cloudflare PoPs never store them; every read is served from R2’s regional store. That guarantees you are exercising R2—not Cloudflare’s CDN—throughout all three phases. At the same time, the huge size eliminates the per request overhead. Using 9 distinct objects mitigates the chance that any single object becomes a bottleneck._

- *Request pattern:* Each worker thread GETs the full object in a tight loop (connection reuse on; no think time) for the entire run.
  - _Large payloads (1 GiB) minimize request count yet still push bandwidth; keep-alive removes TLS handshake overhead and mirrors Amazon S3 best practices for high throughput._

- *Concurrency*: Start at C = 16 connections; ramp upward (+8 every 5 min) until throughput no longer grows or the connection saturates; then hold at the best concurrency for the remainder.
    - *Phases:*
        1.	Warm-up: 5 min at moderate C_{0} = 8 (stabilize connections/paths).
        2.	Ramp: step up C_x - C _{x-1} = 8 every 5 min to find the plateau.
        3.	Steady-state: run at plateau C_{n} for hours to measure the 
    - _Warm-up lets TCP slow-start and TLS session reuse stabilise; ramp finds R2-imposed ceiling; long steady-state captures drift/tail latency. Gradual ramp prevents sudden 429s and mimics AWS “warm-up” guidance.  The threads will round-robin the object keys they fetch. This would avoid creating a single “hot object” bottleneck and instead spread load across multiple keys. There’s no need for complex asynchronous pipelining here because the goal is to maximize throughput per connection for large transfers. We need to verify that the HTTP client library isn’t, for example, defaulting to HTTP/2 and multiplexing all threads over one TCP connection, which could become a bottleneck._

- *Object Storage & Workers:* R2 client with endpoint = `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` in EU. One EC2 in Frankfurt with high bandwidth. 
  - _Avoid the multi-region and multi-client overheads. If NIC counters/CPU/IRQ/Socket errors/No 5 Gb/s flat-line per flow max out before P95 latency jumps, the bottleneck is the EC2._
  
￼
## Metrics Captured

- Throughput (MiB/s, GiB/s) – aggregated per-second.
- Latency – p50/p90/p95/p99 per GET (socket-open → last byte).
- QPS / IOPS – requests per second.
- Error Rates – HTTP 429/5xx, timeouts, retries (with exponential back-off).
- Client Health – NIC Mbps, TCP retransmits, CPU utilisation.


## Test Plan

1.	Provision bucket + objects; launch EC2; install SDK & benchmark driver.
2.	Warm-up for 5 min 8 conns to prime connections.
3.	Ramp: increase C by 8 every 5 min; record throughput; stop when Δthroughput < 5 %.
4.	Steady-state: hold at plateau Cₚ for ≥ 3 h.
5.	Collect logs (CSV/Parquet) + Prometheus scrape.
6.	Post-process: generate throughput timeline, latency CDF, error histogram.


## Tooling

*AWS SDK with CRT:* AWS has optimized S3 clients (e.g., in AWS C++ SDK or experimental CRT for Python) that can automatically use multiple threads and connections for a single transfer ￼. This can saturate 10+ Gbps links by parallelizing data fetching.

*Prometheus:* For live metrics of the system under test and better observability.


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

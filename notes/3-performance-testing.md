## Evaluation Framework

### Key Performance Indicators (KPIs)

| KPI | What It Measures | Metric(s) | Target / Benchmark | Measurement Tooling |
|-----|------------------|-----------|--------------------|---------------------|
| **P99 Object GET latency** | End‑user read latency for a 1 MiB object, measured from EU‐Central‑1 to provider's Frankfurt POP/region. | ms | S3 Standard ≤ 70 ms, R2 ≤ 50 ms | `vegeta`, `curl`, Cloudflare Speedtest Worker |
| **P95 PUT latency (1 MiB)** | Ingest latency under moderate concurrency (32 parallel streams). | ms | S3 ≤ 120 ms, R2 ≤ 90 ms | custom Go harness, `s3-bench` |
| **Sustained upload throughput (multi‑part, 100 GiB)** | Aggregate write bandwidth for data‑lake loads. | MB/s | ≥ 800 MB/s within same region | `s5cmd`, `aws s3 cp`, `rclone` |
| **Durability guarantee** | Probability of object loss over a year. | "n nines" | contractual | provider SLA PDFs |
| **Availability SLA** | % of minutes per month writes/reads succeed. | % | ≥ 99.9 % | provider SLA PDFs |
| **Consistency model** | Visibility of writes. | strong / eventual / read‑after‑write | strong preferred | custom correctness harness |
| **S3 API coverage** | % of official S3 operations that behave identically. | % | ≥ 95 % | `aws‑sdk‑compat` test‑suite |
| **Unit request cost** | $ per 1 M PUT/GET | USD | — | public price sheet |
| **Egress cost** | $ / GiB to Internet | USD | — | public price sheet |
| **Encryption & key‑mgmt capability** | Feature score | tiered | — | documentation analysis |
| **Compliance certifications** | Breadth of attestations | count | SOC 2, ISO 27001, GDPR… | certification portals |

*(Add/remove KPIs as needed per workload.)*

#### Measurement Methodology

1. **Test Regions & Clients**  
   - Primary test region: **eu‑central‑1 (Frankfurt)** for AWS; equivalent EU landing zone for other clouds.  
   - Secondary cross‑continent path: Frankfurt → us‑east‑1 to capture WAN effects.

2. **Object Sizes**  
   - 1 KiB (metadata), 1 MiB (web asset), 64 MiB (Lambda layer), 1 GiB (video segment), 100 GiB (data‑lake multipart).

3. **Run Phases**  
   - *Cold*: first access after 1 h idle to flush caches.  
   - *Warm*: steady‑state 30 min sustained load at 32, 128, and 512 concurrent connections.


4. **Tooling Stack**  
   - `s5cmd`, `rclone`, `vegeta`, `wrk2`, custom Go harness emitting Prometheus metrics.  
   - Time sync via NTP, metrics scraped every 1 s into InfluxDB.

5. **Statistical Treatment**  
   - Discard first 5 % warm‑up samples.  
   - Report P50, P95, P99, max.  
   - 95 % confidence interval via bootstrap.

#### Consistency & Reliability Tests

- **Write‑after‑read watchdog**: repeatedly write a UUID‑tagged object, read until UUID matches, record propagation delay.  
- **Fault‑injection**: abort 5 % of PUTs mid‑flight to measure idempotency and retry semantics.  
- **Durability audit**: upload 1 M checksum‑tagged objects, validate MD5 monthly for 12 months.

### API Compatibility

| Area | Test | Pass Criteria |
|------|------|---------------|
| **Bucket Lifecycle** | Create rule: transition → Glacier/Coldline/Deep Archive | Rule visible in API and enacts transition < 15 min |
| **Multipart Upload** | 10 GiB object split into 10 × 1 GiB parts | Final ETag equals canonical MD5 tree |
| **Pre‑Signed URL** | Generate 10 min GET URL | Object retrievable without auth |
| **Event Notifications** | S3 → SNS/SQS or R2 → Workers queue | Event arrives ≤ 5 s after PUT |
| **ACL & IAM parity** | Apply canned ACL `public-read` | Object accessible via HTTP 200 |
| **Error semantics** | Trigger 404, 403, 412 | Status codes & XML error codes match S3 |

**Scoring**: 2 pts per test (0 = fail, 1 = partial, 2 = full) ⇒ max 12 pts.

### Price Model Evaluation

1. **Load Profiles**  
   - *Low‑traffic static site*: 500 GiB stored, 5 TiB egress/mo, 1 M requests.  
   - *Data‑lake*: 200 TiB stored, 1 TiB egress, 100 M requests, heavy intra‑cloud processing.  
   - *Media CDN origin*: 50 TiB stored, 100 TiB egress.

2. **Cost Components**  
   - Storage $/GB‑month per class/tier.  
   - PUT/GET/DELETE per 10 K requests.  
   - Lifecycle transition, replication, cross‑region fees.  
   - Egress to Internet and to same‑cloud compute.

3. **Scenario Calculator**  
   Spreadsheet pulls unit prices via provider APIs; outputs monthly and annual TCO incl. support plans and redundancy options.

### Security & Compliance KPIs

| Capability | Scoring | Evidence |
|------------|---------|----------|
| **Encryption at rest** | 0 = none, 1 = AES‑256 only, 2 = customer KMS, 3 = HSM | technical docs |
| **Encryption in transit (TLS)** | 0 = < TLS 1.2, 1 = TLS 1.2, 2 = TLS 1.3 | Qualys SSL test |
| **Private Link / VPC endpoint** | 0 = no, 1 = yes | docs |
| **Object Lock / immutability** | 0 = no, 1 = legal hold, 2 = WORM | docs |
| **Compliance** | +1 per: ISO 27001, SOC 2, PCI‑DSS, HIPAA, GDPR, FedRAMP High | audit reports |

_Total security score out of 15._

### Qualitative Criteria

- **Ecosystem Integration** – ETL, serverless, ML, CDN, data‑warehouse hooks.  
- **Developer Experience** – SDK maturity, documentation, CLI/console UX.  
- **Operational Maturity** – observability, audit logs, Terraform/provider coverage, SLA length.  
- **Support & Community** – 24×7 support, dedicated TAM, active forums/Slack.  
- **Vendor Lock‑In Risk** – proprietary features vs S3‑standard, data‑exit ease.

Each rated **1 (poor)** to **5 (excellent)**.

### Weighting & Scoring Method

1. **Weight Matrix**

| Dimension | Weight % |
|-----------|---------|
| Latency & Throughput | 20 |
| Consistency & Reliability | 15 |
| API Compatibility | 10 |
| Price Model | 10 |
| Security & Compliance | 15 |
| Qualitative (5 criteria × 4 % each) | 20 |
| **Total** | **100** |

2. **Scoring Scale**  
   - **5** = best‑in‑class, exceeds benchmark > 25 %.  
   - **4** = meets benchmark.  
   - **3** = adequate, within 10 % of benchmark.  
   - **2** = below benchmark but usable.  
   - **1** = unacceptable for production.

3. **Computation**

```
weighted_score = Σ(criterion_score × criterion_weight)
max_score      = Σ(5 × criterion_weight)
normalized     = (weighted_score / max_score) × 100
```

4. **Visualisation**  
   Radar chart per provider plus stacked bar for TCO.

---

*(Adjust weights or add criteria to match project priorities.)* 
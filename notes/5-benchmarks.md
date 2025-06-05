## Benchmarking

While using the Cloudflare's Object storage can be more cost efficient, it is not the only metric to be concidered before the migration. We want to make sure that the performance of the CloudFlare is also feasible and comparible to the S3 costs.

We want to benchmark the system to show that the Cloudflare infrastructure also has a cutting edge speed and the differenct between the S3 and R2' price is not because in Amazon we pay for a great performance that we will lack in the Cloudflare invironment. 

Since one of the advantages that we have in the R2 is the absence of vendor lock in, we need to check not only the performance of the Object Storage inself, but the end-to-end pipeline with not inly Cloudflare workersl, but also the other VM's for computation. Is Cloudflare R2 fast enough compared with S3? Does free egress offset R2’s request fees? Whether to run compute on Cloudflare Workers or on classic VMs.


## Existing benchmarking solutions

In the BTW25 conference TU Berlin presented a "An Empirical Evaluation of Serverless Cloud Infrastructure for
Large-Scale Data Processing" paper. They performed a detailed analysis of the performance and cost characteristics of serverless infrastructure in the data processing contex. Moreover, they provided an open source framework that enables the integration of the additional benchmarks and cloud infrastructure.

> Our framework includes a comprehensive suite of microbenchmarks for serverless resources and integrates a serverless query engine to run application-level benchmarks. The framework automates the setup, execution, and result processing for the experiments in our evaluation. Hence, it enables the reproduction of our experimental results.


### Results 

### **Skyrise** framework 

| Component (folder) | Purpose | R2 impact |
|--------------------|---------|-----------|
| **`script/benchmark/microbench/`** | Object‑store micro‑benchmarks (size × concurrency × op‑type) | Works out‑of‑the‑box via S3 SDK. |
| **`script/query_engine/`** | Serverless SQL engine that runs TPC‑H on S3 + Lambda | Swap SDK endpoint to R2; optional: replace Lambda launcher with Workers. |
| **`experiment/*.yaml` (Framefort)** | Declarative matrix: `{storage cfg, compute cfg, workload}` | Add a new stanza `provider: r2-production`. |
| **`cost_model.yaml`** | Unit prices & aggregation logic | Set `egress_price_gb: 0`, update Class‑A/B and storage rates. |
| **`plotting/`** | Generates CSV + Matplotlib figures | Same scripts; new R2 run drops automatically into charts. |

*Screenshot #1 – insert after this table: directory tree of `script/benchmark/experiment/` showing the YAMLs.*

---

## 3 What the Berlin group already tested on S3  

| Bucket | Workload matrix | Repeats | Peak data | AWS bill |
|--------|-----------------|---------|-----------|----------|
| **Micro‑bench** | 5 object sizes (1 KB → 1 GB) × 6 concurrency levels (1 → 4096) × **PUT/GET** | 3 | ≈ 90 GB in / 90 GB out | USD 18 (S3) |
| **End‑to‑end** | TPC‑H SF {10, 100, 300} × 22 queries | 3 | ≈ 2.4 TB read | USD 42 (S3 egress) + USD 8 (Lambda) |

*(Source: EDBT ’25 paper 239 & Skyrise repo.)*

*Screenshot #2 – latency/throughput heat‑map from `experiment/results/*png`.*

---

## 4 How to extend Skyrise for R2  

1. **Fork** `hpides/skyrise`.  
2. **Add storage config**  

   ```yaml
   # experiment/storage_r2.yaml
   name: r2
   kind: s3-compatible
   endpoint: https://<account>.r2.cloudflarestorage.com
   region: auto
   creds: ${R2_ACCESS_KEY}:${R2_SECRET_KEY}
   pricing:
     class_a_per_m: 4.50
     class_b_per_m: 0.36
     storage_gb_month: 0.015
     egress_gb: 0        # Free!
   ```  

3. **(Optional) new compute provider** – implement `workers_provider.py` that satisfies Skyrise’s `Provider` interface (`deploy`, `invoke`, `collect_logs`). Register it in `providers/__init__.py`.  
4. **Edit experiment matrix**  
   - Duplicate `experiment/s3_microbench.yaml` → `r2_microbench.yaml`; change `storage: r2`.  
   - Duplicate `experiment/tpch_s3.yaml` → `tpch_r2.yaml`; switch both `storage` and (if using Workers) `compute`.  
5. **Run**  

   ```bash
   framefort run experiment/r2_microbench.yaml
   framefort run experiment/tpch_r2.yaml
   ```  

6. **Collect & compare** – new result CSVs appear under `results/r2/*`. Existing plotting scripts overlay S3 and R2 automatically.

*Screenshot #3 – sample YAML diff highlighting the three changed lines.*

---

## 5 Ensuring comparability with the S3 baseline  

| Aspect | Action for R2 run |
|--------|------------------|
| **Object sizes / concurrencies** | Keep **exactly** `sizes=[1k,64k,1M,64M,1G]`, `concurrency=[1,8,64,256,1024,4096]`. |
| **Repetitions** | Same `n=3` to match CI width. |
| **Function memory tier** | Choose Cloudflare Workers 128 MB (≈ Lambda 128 MB) or note deviation. |
| **Request mix** | PUT‑then‑GET; same write/read ratio as S3 run. |
| **Metrics** | Export the canonical CSV schema (`lat_p50, lat_p95, throughput, cost`). |
| **Charts** | Re‑run `plot_results.py`; screenshot comparison charts. |

---

## 6 Why the Berlin S3 study is directly reusable  

* **Methodology identical** (size‑sweep + concurrency‑sweep → throughput plateau).  
* **Framework identical** (Skyrise); no code drift.  
* **Cost model templated** – plug in R2 prices → apples‑to‑apples \$ comparison.  
* **Publication‑ready baselines** – citing their peer‑reviewed numbers strengthens our report; we only add *“what changes when egress is free.”*

*Screenshot #4 – include the paper’s cost‑break‑even plot; reference Fig. 7 in the PDF.*

---

## 7 Next steps & deliverables  

1. **Demo run** with R2 micro‑bench (confirm scripts, collect preliminary CSV).  
2. **Align with mentor** on whether to include Workers compute or keep compute on local VM.  
3. **Full experimental sweep** → push `results/r2/*` and updated plots.  
4. **Write “Findings” subsection**: speed gap, cost delta, break‑even analysis.  
5. **Update migration‑cost chapter** with the new *real* Class‑A/B counts from the micro‑benchmarks.

---
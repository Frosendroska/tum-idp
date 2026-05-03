[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Frosendroska/tum-idp)

# Replacing AWS S3 with Cloudflare R2: Cost Analysis and Feasibility Study

**TU Munich — Interdisciplinary Project (IDP) · Ekaterina Braun · April 2026**

## Abstract

Amazon S3’s egress fees—starting at $0.09 per GB—are a major cost driver for bandwidth-intensive cloud workloads. Cloudflare R2 eliminates these fees and provides an S3-compatible API, but its performance under sustained high-concurrency and high-bandwidth conditions remains insufficiently characterised.

We present a benchmarking framework designed to saturate high-bandwidth network interfaces from a single Python client using process-level parallelism, asynchronous I/O, and HTTP request pipelining. Using this framework, we conduct ten experiments across six EC2 instance types (10 - 200Gbps) and complement the measurements with a structured cost and migration analysis.

In our setup, R2 saturates a 15 Gbps interface at 95 % utilization without observable throttling. At higher bandwidths, throughput becomes client-limited, reaching up to 114~Gbps. Long-running experiments on instances with non-guaranteed network bandwidth reveal a throughput drop after around 30 minutes under sustained load, indicating that short benchmarks may overestimate steady-state performance. Tail latency increases with concurrency, with pre-transfer delays accounting for up to 62 % of mean request time at saturation. Reducing request size from 100 MB to 50 MB at constant aggregate throughput improves peak-concurrency RTT by up to 96 %, highlighting request granularity as a primary lever for latency control.

A cost analysis shows 53 - 77 % savings compared to S3 for egress-heavy workloads, with migration break-even typically within one to four months. For large-object, high-concurrency workloads, R2 achieves throughput comparable to S3 at single-client scale under client-limited conditions. These findings do not generalize to small-object or multi-client scenarios.

## Links

- **Report (PDF):** [report/Replacing-AWS-S3-with-Cloudflare-R2-Cost-Analysis-and-Feasibility-Study-report.pdf](report/Replacing-AWS-S3-with-Cloudflare-R2-Cost-Analysis-and-Feasibility-Study-report.pdf)
- **Report (Overleaf):** [overleaf.com/Ekaterina-Braun-IDP](https://sharelatex.tum.de/read/gskhscwmfptn#fe9e71)

- **Presentation slides & transcript:** [report/presentation/](report/presentation/)
- **Google Sheets:** [Google Sheets](https://docs.google.com/presentation/d/1xxCk1pUvnaJTkFJJCEnNik8FU2yyVuylQ4l7zmhHX3o/edit?usp=sharing)

- **Project description:** [Google Docs](https://docs.google.com/document/d/1j7r3w-ZQyOZsmdqYzyyUJghaHzooTu6h3ejlI9FZICs/edit?tab=t.0#heading=h.uzx2xxidnmp0)
- **Project notes:** [notes/](notes/)

## Repository Structure

```
tum-idp/
├── R2-bench/               # Benchmarking framework
│   ├── cli.py              # Main entry point
│   ├── algorithms/         # Plateau detection & concurrency ramp logic
│   ├── common/             # HTTP client, metrics collection
│   ├── systems/            # R2 and S3 connector implementations
│   ├── r2-results/         # Raw experiment results (parquet)
│   ├── s3-results/         # S3 baseline results (parquet)
│   ├── r2-plots/           # Generated throughput & latency plots
│   └── EXPERIMENT_SETUP.md # Experiment log and configuration details
│
├── report/                 # LaTeX report source
│   ├── main.tex            # Root document
│   ├── chapters/           # Chapter .tex files (01–08)
│   ├── figures/            # All plots and diagrams
│   ├── report.pdf          # Compiled report
│   └── presentation/       # Defence presentation
│       ├── slides.md       # Slide-by-slide descriptions
│       └── transcript.md   # Full speaker notes
│
├── notes/                  # Project notes by phase
└── PLAN.md                 # Original project plan and timeline
```

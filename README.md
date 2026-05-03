[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Frosendroska/tum-idp)

# Replacing AWS S3 with Cloudflare R2: Cost Analysis and Feasibility Study

**TU Munich — Interdisciplinary Project (IDP) · Ekaterina Braun · April 2026**

## Abstract (short)

This project evaluates the feasibility and cost implications of replacing Amazon S3 with Cloudflare R2 as an object storage backend. Cloudflare R2 offers an S3-compatible API and eliminates egress fees entirely, making it a compelling alternative for egress-heavy workloads such as ML pipelines, media delivery, and data archives.

A custom Python benchmarking framework (r2-bench) was developed to measure R2 throughput and latency from EC2 instances across six instance types (4–128 vCPUs, 10–200 Gbps) using a three-phase adaptive methodology. Key findings: R2 saturated a 15 Gbps NIC at 95% efficiency with no observable throttling; at higher bandwidths the Python client was the bottleneck, establishing 114 Gbps as a lower bound on R2's capacity. Under high concurrency, latency degrades proportionally and predictably — at saturation, 62% of request time is pre-transfer queueing. Smaller request chunks (50 MB vs 100 MB) reduce RTT by 96% at equal throughput. Regional routing matters: Stockholm outperformed Frankfurt by 14% in average throughput, with Frankfurt's tail latency (P95) 78–83% higher at peak load.

Cost modelling shows 53–77% monthly savings over S3 depending on egress volume, with migration break-even in 1.6–5 months across representative workload scales.

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

# Benchmarking

Although Cloudflare R2 is often more cost-effective than Amazon S3, cost alone shouldn’t drive our migration decision. We must confirm that R2 delivers performance on par with S3 so that the price gap isn’t the result of higher latency or lower throughput.

Our benchmark should therefore evaluate the entire end-to-end pipeline—not just R2’s raw object-storage performance, but also Cloudflare Workers and any computation running on external VMs. Specifically, we need to answer:
	•	Is Cloudflare R2 fast enough relative to S3?
	•	Does zero-egress pricing outweigh R2’s request fees?
	•	Should compute run on Cloudflare Workers or remain on traditional VMs?

Addressing these questions will show whether we can gain R2’s vendor-neutral benefits without sacrificing speed or incurring hidden costs.


## Existing benchmarking solutions

### Skyrise

In the BTW25 conference TU Berlin presented a "An Empirical Evaluation of Serverless Cloud Infrastructure for
Large-Scale Data Processing" paper. They performed a detailed analysis of the performance and cost characteristics of serverless infrastructure in the data processing contex. Moreover, they provided an open source framework that enables the integration of the additional benchmarks and cloud infrastructure.

> Our framework includes a comprehensive suite of microbenchmarks for serverless resources and integrates a serverless query engine to run application-level benchmarks. The framework automates the setup, execution, and result processing for the experiments in our evaluation. Hence, it enables the reproduction of our experimental results.


### Results 

| Service                     | Max Aggregate Throughput (Read / Write)            | IOPS (Read / Write) on New Setup | Read Latency (Median | p95) | Notes |
|----------------------------|-----------------------------------------------------|----------------------------------|----------------------|------|-------|
| S3 Standard                | ~250 / ~250 GiB/s (linear scaling with clients)     | ~8k / ~4k ops/s                  | ~27 ms | ~75 ms       | Highest tail latency; outliers >10 s. |
| S3 Express One Zone        | ~250 / ~250 GiB/s (similar scaling to Standard)     | ~220k / ~42k ops/s               | ~5 ms | ~5 ms        | Low and consistent latency; higher request cost. |
| DynamoDB (on-demand)       | ~0.38 / ~0.03 GiB/s (saturates early)               | ~16k / ~9.6k ops/s               | ~5 ms | (more variable) | Ultra-low median latency; poor bulk throughput/cost. |
| EFS (per filesystem)       | ~20 / ~5 GiB/s (hits per-FS quotas)                 | Well below per-FS quotas; limited scaling | ~5 ms | ~5 ms | Writes ~2–3× slower than reads; doubling with 2 FS only. |


#### Reuse

 Skyrise codebase a bit heavyweight for our needs, so we borrowed their overall setup and ideas but wrote a simpler microbenchmark from scratch. 
 It is implemented in the [direct_storage_benchmark.cpp](https://github.com/Frosendroska/skyrise/edit/no-brain-r2-microbenchmark/src/benchmark/bin/micro_benchmark/direct_storage_benchmark.cpp?pr=%2Fhpides%2Fskyrise%2Fpull%2F1) file in the [repo](https://github.com/hpides/skyrise/pull/1).

*Purpose:* Microbenchmark for measuring upload and download performance of Cloudflare R2 object storage using the AWS S3 SDK.
*Key Features:*
- Multi-threaded operations: Supports configurable thread counts for parallel uploads/downloads
- Two-phase testing:
    - Type A: Upload operations (writes)
    - Type B: Download operations (reads)
- Comprehensive metrics: Measures latency (min/max/avg), throughput, and wall-clock timing
- Configurable parameters: Object size, operation counts, number of runs, bucket/prefix settings
- Main Components:
    - R2Benchmark class handles AWS S3 client setup and benchmark execution
    - CLI interface using CLI11 library for parameter configuration
    - Thread-safe latency collection with mutex protection
    - Random data generation for test objects
*Usage:* The tool uploads objects to R2 storage, then downloads them while measuring performance metrics, making it useful for evaluating R2 storage performance characteristics under different workloads and configurations.

We run this script with the following parameters for the proof of concept:

```
Type A (upload) ops:    1000  
Type B (download) ops:  10000  
Object size:            1024 bytes (1 KB)  
Threads:                8  
Runs:                   1  
```

The results are in the (benchnark_plot/)[https://github.com/hpides/skyrise/tree/9d58f82f3c5ba39fe9e181fef4a984cdc49da731/benchmark_plots] folder:

#### Benchmark Summary Report

![](../images/skyrise/latency_boxplot.png)
![](../images/skyrise/read_latency_distribution.png)
![](../images/skyrise/write_latency_distribution.png)
![](../images/skyrise/throughput_comparison.png)

The low throughput is expected—it’s just a basic proof of concept. On top of that, the tests were run from a personal laptop, not from EC2 or R2 workers.

However, we now have an impression of the latency distribution and can build a more reliable microbenchmark. 


## Our benchmark solution

### Throughput banchmarks

Our next step is to run more comprehensive experiments from EC2, where we’ll store data in R2 and fetch it from the EC2 instance to test both microbenchmarking and throughput limits. The implementation and the design document are in `R2-bench/` folder.

The design document of this benchmarking is in (README.md)[R2-bench/README.md].

#### Results

**For 100 MB chunks:**

- r5.xlarge (32 GiB, 4 vCPUs, EBS only, Up to 25 Gigabit, $0.298 hourly)
  - The results are in the [r5.xlarge](../plots/r5.xlarge/) folder.
    Summary:
    ```
    Phase        Duration     Requests     Data (GB)    Throughput      Req/s      Latency (ms)    Concurrency 
    ----------------------------------------------------------------------------------------------------
    warmup       60.3         310          30.273       4315.13         5.14       1567.3          8           
    ramp_1       304.1        1604         156.641      4424.23         5.27       1503.5          8           
    ramp_2       305.5        2015         196.777      5532.15         6.59       6044.0          41          
    ramp_3       307.2        2111         206.152      5764.01         6.87       10429.6         73          
    ramp_4       285.4        1964         191.797      5772.15         6.88       15095.9         104         
    ALL          1261.4       8004         781.641      5322.92         6.35       8338.5          57            
    ```
    ![](../R2-bench/plots/r5.xlarge/per_second_throughput_timeline.png)

- c5n.9xlarge (96 GiB, 36 vCPUs, EBS only, 50 Gigabit, $1.944 hourly)
  - The results are in the [c5n.9xlarge](../plots/c5n.9xlarge/) folder.
    Summary:
    ```
    Phase        Duration     Requests     Data (GB)    Throughput      Req/s      Latency (ms)    Concurrency 
    ----------------------------------------------------------------------------------------------------
    warmup       60.7         338          33.008       4673.78         5.57       1438.0          8           
    ramp_1       303.0        1370         133.789      3792.27         4.52       1755.0          8           
    ramp_2       303.3        3557         347.363      9839.12         11.73      3399.2          40          
    ramp_3       303.9        3548         346.484      9794.84         11.68      6148.1          73          
    ramp_4       292.8        3390         331.055      9711.35         11.58      8992.2          104         
    ALL          1261.9       12203        1191.699     8112.24         9.67       5513.3          63      
    ```
    ![pic](../R2-bench/plots/c5n.9xlarge/per_second_throughput_timeline.png)

- c6in.16xlarge (128 GiB, 32 vCPUs, EBS only, 100 Gigabit, $3.6288 hourly)
  - The results are in the [c6in.16xlarge](../plots/c6in.16xlarge/) folder.
    Summary:
    ```
    Phase        Duration     Requests     Data (GB)    Throughput      Req/s      Latency (ms)    Concurrency 
    ----------------------------------------------------------------------------------------------------
    warmup       59.5         369          36.035       5198.37         6.20       1304.4          8           
    ramp_1       301.0        1812         176.953      5049.59         6.02       1324.9          8           
    ramp_2       302.6        5320         519.531      14747.04        17.58      2270.0          40          
    ramp_3       303.2        5168         504.688      14298.46        17.05      4210.0          72          
    ramp_4       295.3        5390         526.367      15313.51        18.26      5701.6          104         
    ALL          1261.5       18059        1763.574     12008.27        14.31      3734.8          65    
    ```
    ![pic](../R2-bench/plots/c6in.16xlarge/per_second_throughput_timeline.png)

- hpc7a.12xlarge (128 GiB,	64 vCPUs, EBS only, 300 Gigabit, $8.8292 hourly)
  - The results are in the [hpc7g.16xlarge](../plots/hpc7g.16xlarge/) folder.
    Summary:
    ```
    Phase        Duration     Requests     Data (GB)    Throughput      Req/s      Latency (ms)    Concurrency 
    ----------------------------------------------------------------------------------------------------
    warmup       60.6         326          31.836       4514.45         5.38       1488.8          8           
    ramp_1       302.2        1632         159.375      4530.14         5.40       1474.3          8           
    ramp_2       304.6        2798         273.242      7705.03         9.19       4331.9          40          
    ramp_3       305.4        2694         263.086      7400.75         8.82       8137.0          73          
    ramp_4       289.7        2528         246.875      7319.00         8.72       11927.1         104         
    ALL          1261.9       9978         974.414      6632.83         7.91       6723.3          59     
    ```
    ![pic](../R2-bench/plots/hpc7g.16xlarge/per_second_throughput_timeline.png)




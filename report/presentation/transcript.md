# Presentation Transcript — Speaker Notes

**22 slides total — 21 spoken (~15 min) + slide 22 silent (on screen during Q&A).**  
**Backup slides** (c6in plot, Literature, When R2 makes sense) sit after slide 22 — pull during Q&A if needed.

---

## Slide 1 — Title (~30 sec)

"Good morning. My name is Ekaterina Braun, and today I'm presenting my IDP: Replacing AWS S3 with Cloudflare R2.

The question I'm answering stays in front of a lot of engineering teams: is there a cheaper, fully compatible alternative to S3 — and is it actually fast enough for production? In the next 15 minutes, I'll give you a concrete, empirical answer. Let's start with the problem."

---

## Slide 2 — The Real Cost of Object Storage (~45 sec)

"Cloud storage bills have three parts — and they are not created equal.

Storage: about 2.3 cents per gigabyte per month. Predictable.

Operations: 40 cents per million GETs. Also fine.

Then egress — 9 cents per gigabyte every time you serve data to the internet. That scales linearly with how popular your service is. For egress-heavy workloads — media delivery, ML training data, backups — egress dominates the bill. It's a tax on growth."

---

## Slide 3 — A Radical Alternative: Cloudflare R2 (~40 sec)

"Cloudflare's answer is radical: same S3-compatible API, and zero egress fees — none, free, forever. On top of that, storage is 35% cheaper, API calls are 10% cheaper, and they match S3's eleven nines of durability, generous free tier.
"

---

## Slide 4 — But Is It Actually Viable? (~30 sec)

"
So on paper this almost sounds too good — no egress, cost savings, compatible API. But there's one thing nobody had properly answered before this study. 

Is it fast enough under real conditions? What are the benchmarks under high load? That tension is what this project is built around."

---

## Slide 5 — Research Questions (~35 sec)

"I formalized this into three questions.

**Throughput** — can R2 saturate high-bandwidth EC2 links?

**Latency** — what happens under high concurrency?

**Cost** — is migration economically worth it?

These three structure everything you're about to see."

---

## Slide 6 — Scope of This Study (~45 sec)

"Before results, let me be precise about scope — because it determines how to read everything that follows.

Single client. One EC2 instance. 

The workload: 50 to 100 MB byte-range GETs 
from a single object, with random offsets per request. 
This means Cloudflare's CDN cannot cache anything — every request hits R2's storage backend directly. That is important because we dont want to measure caching layer.

Six EC2 instance types, 10 to 200 Gbps."

---

## Slide 7 — Benchmarking Methodology (~30 sec)

"Every experiment runs automatically through three phases.

Warm-up: TCP connections stabilize, TLS sessions are cached, cold-start effects are gone before anything is measured.

Ramp-up: concurrency increases, throughput measured at each level, stops when it plateaus.

Steady-state: extended run at the optimum."

---

## Slide 8 — Plateau Detection (~25 sec)

"How does the ramp know when to stop? Three mechanisms run in parallel: bandwith ceiling in the instance, degradation from the peak, a relative improvement check over the last N steps. Any one firing stops the ramp — an OR-gate.

The result: the framework finds the optimal concurrency per instance automatically. No manual tuning."

---

## Slide 9 — Custom Benchmarking Client (~30 sec)

"Saturating 100+ gigabit links is a very complicated technical challenge. For our client it also means solving the Python's Global Interpreter Lock problem that prevents multi-core parallelism from a single process.

My solution: a three-tier hierarchy. One process per vCPU — bypassing the GIL. Async coroutines within each process. HTTP pipelining per coroutine. Thousands of simultaneous in-flight requests. 
Results are written to Parquet for offline analysis."

---

## Slide 10 — Throughput Results (~65 sec)

"Here are the full results. The two columns that tell the bottleneck story are Achieved and Needed — the per-core throughput the client actually delivered versus what's required to saturate the NIC.

We will return to these preperties later, now I want you to notice the max discovered throughput. It is 114 Gbps on the c6in.32xlarge. 

AWS documents roughly 100 Gbps for S3 from a single EC2 instance — we're in the same order of magnitude.
"

---

## Slide 11 — The Client Is the Bottleneck. Not R2. (~45 sec)

"The Python client was the bottleneck in some experiments.

CPU was fully utilized across all cores at peak. The NIC had headroom. 
There's a clear per-core ceiling that falls as you add more cores — Python's coordination overhead compounds at scale.

At 16 vCPUs: to saturate a 15 Gbps NIC the needed throughput is within Python's reach. NIC fills first. 
At 128 vCPUs: you'd need more than Python can give to saturate 200 Gbps. CPU gives out.

114 Gbps is a lower bound on R2's capacity. Not a ceiling."

---

## Slide 12 — Client Keeps Up, R2 Link Saturated (~20 sec)

*[Let the plot speak.]*

"This is what clean saturation looks like. 15 Gbps. Steady ramp, plateu at Ninety-five percent of the NIC."

---

## Slide 13 — Short Benchmarks Lie. The Bandwidth Cliff. (~50 sec)

"
AWS 'up to N Gbps' instances have a burst credit mechanism. You get elevated bandwidth for a while, then when the credit runs out, you drop hard. No gradual fade. A step.

I ran long experiments specifically to catch this. The r8gd.4xlarge held at 14.3 Gbps for 30 minutes, then permanently dropped to 7.1 Gbps."

---

## Slide 14 — Two Latency Metrics (~35 sec)

"Before the latency results, I want to establish two distinct metrics.

RTT, or time-to-first-byte: the time from issuing the GET to receiving the very first response byte, before any body is read. Critically, RTT is independent of chunk size — a 50 MB and a 100 MB request have the same RTT if the system state is the same. RTT captures network round-trip, backend processing, and queueing pressure. It's the diagnostic signal.

Total latency adds the body download on top. It scales with chunk size, so it reflects both system pressure and download volume.

With that clear, let's look at what happened."

---

## Slide 15 — Latency Increases with Concurrency (~45 sec)

"The staircase on this plot is the core result. Every time concurrency steps up, latency steps up — cleanly, predictably.
And despite the degradation, the system held. Across all experiments, 100% post-retry success. 

During almost no load RTT was around 120 milliseconds and median latency about 1.6 seconds. Comparable to S3 in the same conditions.
Under load, at four times the concurrency, latency grows roughly proportional. This is exactly what Little's Law predicts.
"

---

## Slide 16 — At Saturation, 62% of Request Time Is Waiting (~40 sec)

"Now zoom into RTT specifically at saturation — and look at what that number reveals.

At peak concurrency the mean request took 9.5 seconds total. Of that, only 38% was transferring data. The other 62% was RTT.

RTT elevated because requests queue up faster than R2 can respond, NOT because the download itself is slow. So reducing queue depth matters more than increasing bandwidth.

This directly motivates the next result."

---

## Slide 17 — Request Granularity Matters (~50 sec)

"
Two configurations on the same instance, with identical total in-flight data: 100 MB chunks at pipeline depth 3, and 50 MB chunks at pipeline depth 6. 

Aggregate throughput is essentially identical at about 110 Gbps.

RTT at peak concurrency RTT is 96% lower for 50MB than for 100MB. Total latency is 55% lower.

-The mechanism: smaller chunks complete faster, so fewer requests are queued at any moment. Lower queue depth — shorter wait.-

Takeaway: Chunk size is the most impactful latency lever — without touching throughput."

---

## Slide 18 — Geography Matters: Frankfurt vs Stockholm (~45 sec)

"Let me compare the two regions directly. Same hardware same chunk config, same R2 bucket. EC2 in Stockholm and Frankfurt, side by side.

Throughput is 14% lower, and Frankfurt needed twice the concurrency to get there.

RTT median is actually comparable. But the tail RTT and total latency diverges sharply.

Frankfurt's routing path to Cloudflare's infrastructure is less stable under load. So, measure where you deploy."

---

## Slide 19 — Cost Analysis (~50 sec)

"Now the money.

Of course, it is hard to generalize this, because the numbers highly depend on the workload. 
But lets walk through some examples.

For a large workload — 100 TB stored, 50 TB egress per month, it's 77% mounthly savings, after $8,000 one time migration costs. Therefore break-even is in under 2 months.

And these aren't hypothetical. VSCO migrated 2 petabytes of user images to R2 and reported $400,000 in annual cloud savings."

---

## Slide 20 — Key Takeaways (~55 sec)

"Three questions, three answers.

**Throughput.** R2 delivered — 95% NIC utilization at 15 Gbps, 100% success rate, no throttling across ten experiments. At higher bandwidths the Python client was the bottleneck, not R2. 114 Gbps is a lower bound. 

**Latency.** At no load, R2 behaves like S3 — 120 ms RTT, 1.6 s median. Under high concurrency, degradation is proportional and stable. At saturation, 62% of request time is pre-transfer queueing — not the download. Chunk size is the lever: 50 MB cuts RTT by 96% at equal throughput.

**Cost.** Huge monthly savings. Break-even in a couple of months. For large-object, egress-heavy workloads: the case is strong."

---

## Slide 21 — Future Work (~30 sec)

"The next steps are well-defined.

A compiled client removes the Python bottleneck and tells us where R2's actual ceiling is. 
More regions and instance types extend R2's characterisation — the framework is ready, it just needs running.
Network-level diagnostics will let us attribute the Frankfurt slowdown precisely.
An S3 baseline gives a controlled head-to-head comparison.  
Broadening to multi-object workloads and write throughput would complete the picture.

Thank you. I'm happy to take questions."

*[Advance to slide 22. Say nothing. Leave it on screen for the entire Q&A.]*

---

## Slide 22 — Client vs R2: What Limits What

*[Silent — no speech. This slide stays on screen throughout Q&A.]*

---

## Q&A — Anticipated Questions

**Q: Is 114 Gbps actually R2's limit?**
> Almost certainly not. CPU was at 99% while the NIC sat at 55%. 114 Gbps is a lower bound — it reflects the Python client's ceiling, not R2's backend capacity. A compiled client would push this higher.

**Q: How do your results compare to S3?**
> We have earlier S3 data showing comparable throughput and latency at the same concurrency levels — S3 was also client-limited. AWS documents roughly 100 Gbps from a single EC2 instance, same order of magnitude. Since both are client-limited, the similarity reflects shared client-side constraints, not either system's true backend ceiling. The S3 data was from an earlier framework version, so we use it only for order-of-magnitude comparison.

**Q: What about reliability? Does R2 ever fail under load?**
> In all ten experiments: 100% post-retry success. The highest measured retry rate was 0.048% on the r8gd.4xlarge long-run. Remarkably stable. That said, retries mask transient errors — applications that cannot tolerate automatic retries face a small but non-zero transient failure rate at high concurrency.

**Q: Why Frankfurt 14% slower than Stockholm?**
> We attribute it to network path quality differences between AWS and Cloudflare's infrastructure — Frankfurt needed 2× the concurrency to reach peak throughput and averaged 89 Gbps versus Stockholm's 104 Gbps. Without traceroute data or RTT baselines to individual Cloudflare PoPs we can't identify the cause. Practical implication: measure in your own region before assuming Stockholm results apply elsewhere. This is explicitly listed as future work.

**Q: How do you know R2 wasn't softly throttling you?**
> We can't fully rule out undisclosed per-account limits. But we saw no signatures: throughput was stable at plateau, retry rates below 0.05%, performance scaled predictably with concurrency. If there were soft limits, they were above 114 Gbps. A compiled client would be the definitive test.

**Q: Why a single 9 GB object?**
> Deliberate design choice: we want to measure R2's storage backend, not its metadata index or prefix routing. A single object with random range offsets forces every request to the storage layer — no caching, no hot-key effects. The limitation is real: we don't know how R2 behaves across many objects or prefixes. Multi-object workloads are item 5 in the future work list.

**Q: What is the network path to Cloudflare?**
> We don't know — that's a genuine blind spot. All measurements are client-side. We can't say which Cloudflare PoP handled requests or how much RTT was propagation versus backend processing. Network-level diagnostics are explicitly listed as future work.

**Q: You only tested downloads. What about uploads?**
> Uploads are explicitly out of scope. AWS documents a hard IGW cap for upload traffic: 5 Gbps for instances below 32 vCPUs. That cap would likely bottleneck uploads before R2 does. Write throughput is listed as future work.

**Q: Could you have used an existing benchmark tool?**
> I evaluated existing tools early. Most are single-process and hit the GIL ceiling immediately. Compiled-language tools don't support the three-phase adaptive methodology — they use fixed concurrency, so you'd miss the plateau entirely and need manual tuning per instance. R2-bench was necessary for consistent, comparable results across six very different instance types.

**Q: What concurrency level is right for production?**
> Depends on instance type and chunk size — that's exactly what the ramp-up phase discovers. For a 16-vCPU instance with 50 MB chunks, the plateau was around C192 to C288. For 128 vCPUs it was C768. Operate just below the plateau: at the plateau, you add latency without adding throughput. Run the ramp-up once per configuration — the framework outputs the optimal level directly.

**Q: What if Cloudflare changes its pricing?**
> There's no contractual guarantee that zero egress stays zero. Cloudflare has maintained it since 2022 and positioned it as a strategic differentiator. The real hedge is the S3-compatible API: switching back to S3 or to another S3-compatible provider has low technical switching cost. The main migration risk is the one-time egress cost out, not lock-in.

**Q: What literature covered this before?** *(pull Backup Slide B)*
> Four references shaped the context. Skyrise from TU Berlin showed S3 scales to 250 GiB/s — but across hundreds of distributed clients. Tigris showed R2 is 28× slower than S3 for 1 KB objects. Cloudflare's own benchmark showed R2 has 38% lower P95 for geographically distributed 1 MB access. Su et al. gave us the queueing-theory foundation. Our gap: nobody had studied single-client, large-object, sustained high-bandwidth workloads from EC2 to R2.

**Q: When should someone actually migrate?** *(pull Backup Slide C)*
> Strong case: large objects, batch workloads, high egress volumes — ML pipelines, media delivery, data archives. R2 was built for this. Think twice: small objects under 1 MB where R2's latency is much worse; latency-sensitive interactive APIs; workloads deeply tied to S3-specific features like Object Lock or S3 Select.

**Q: The c6in concurrency plot — can you show it?** *(pull Backup Slide A)*
> This is the c6in.16xlarge at 100 Gbps. Throughput peaks at C384 and then plateaus — adding more connections beyond that only adds latency without adding throughput. The ceiling is the CPU, not R2.

# Limitations

#### Terms Of Service CloudFlare

1. [Cloudflare Website and Online Services Terms of Use](https://www.cloudflare.com/en-gb/website-terms/) "We may at our sole discretion suspend or terminate your access to the Websites and/or Online Services at any time, with or without notice for any reason or no reason at all. We also reserve the right to modify or discontinue the Websites and/or Online Services at any time (including, without limitation, by limiting or discontinuing certain features of the Websites and/or Online Services) without notice to you. We will have no liability whatsoever on account of any change to the Websites and/or Online Services or any suspension or termination of your access to or use of the Websites and/or Online Services." 
  
2. [Service Specific Terms](https://www.cloudflare.com/en-gb/service-specific-terms-application-services/) “Cloudflare reserves the right to disable or limit your access … if you serve video or a disproportionate percentage of large files without the appropriate Paid Services.” 

3. [R2 Specific Terms](https://www.cloudflare.com/en-gb/service-specific-terms-developer-platform/#developer-platform-terms)

4. [Cloudflare Service Level Agreement](https://www.cloudflare.com/en-gb/business-sla/) Commits to a **100 % uptime guarantee**. Customers are eligible for compensation that is calculated as following: `Service Credit = (Outage Period minutes * Affected Customer Ratio) ÷ Scheduled Availability minutes`


#### Terms Of Service Amazon

1. [AWS Customer Agreement](https://aws.amazon.com/agreement/) "We may suspend or terminate your right to access or use any portion or all of the Service Offerings immediately upon notice to you if we determine that: (a) your use of the Service Offerings poses a security risk to us or any third party; (b) your use could adversely impact the Service Offerings, the systems or Content of any other AWS customer; (c) your use subjects us, our affiliates, or any third party to liability; or (d) you are in breach of this Agreement or have failed to pay Fees."

2. [AWS Service Terms — Amazon Simple Storage Service](https://aws.amazon.com/service-terms/#amazon-simple-storage-service) "You are solely responsible for the development, content, operation, maintenance, and use of Your Content … You will ensure that Your Content and your use of the Service Offerings comply with the AWS Acceptable Use Policy and the other Policies." Amazon also reserves the right to change or discontinue any Service Offerings and to modify prices upon at least 30 days’ advance notice.

3. [Amazon S3 Service Level Agreement](https://aws.amazon.com/s3/sla/) Commits to a **99.9 % Monthly Uptime Percentage**; the *sole remedy* for breaches is a **service credit**, and Amazon otherwise disclaims additional liability.


## S3 Official Limitations

> [Amazon Docs](https://docs.aws.amazon.com/general/latest/gr/s3.html);
> [User Guide, Object Keys]( https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-keys.html);
> [User Guide, Using Metadata](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingMetadata.html?utm_source=chatgpt.com);
> [User Guide, Bucket Restrictions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/BucketRestrictions.html)


* **General-purpose buckets per account** – 10 000 by default (can be raised on request) 
* **Object size** – up to 5 TB per object (160 GB if you upload through the console UI) 
* **Multipart upload**  
  * 10 000 parts per object    
  * 5 MB minimum part size / 5 GB maximum part size  
* **Object key length** – 1 024 bytes max 
* **Object metadata** – 2 KB user-defined + 2 KB system-defined (8 KB total request header)
* **Bucket size / object count** – No hard limit; unlimited storage in a bucket

## R2 Official Limitations

> [R2 Documentation Limits](https://developers.cloudflare.com/r2/platform/limits/#public-bucket-rate-limiting)

* **Buckets per account** – 1 000 000    
* **Data storage per bucket** – Unlimited  
* **Bucket management operations** – 50 ops / s per bucket  
* **Custom domains per bucket** – 50  
* **Object key length** – 1 024 bytes  
* **Object metadata** – 8 192 bytes (8 KB)  
* **Object size** – 5 TiB per object (4.995 TiB effective)    
* **Single-request upload size** – 5 GiB (4.995 GiB)  
* **Multipart upload parts** – 10 000  
* **Concurrent writes to same key** – 1 write / s (rate-limits above that) 

## Side-by-side comparison

| Limitation | Amazon S3 (official) | Cloudflare R2 (official) |
|------------|----------------------|--------------------------|
| Data storage per bucket | Unlimited | Unlimited |
| Buckets per account | 10 000 (default; adjustable) | 1 000 000 |
| Object key length | 1 024 bytes | 1 024 bytes |
| Object size limit | 5 TB | 5 TiB (4.995 TiB) |
| Single-request upload size | 160 GB (console) / 5 GB part max | 5 GiB (single request) |
| Multipart parts per object | 10 000 | 10 000 |
| Multipart part size | 5 MB – 5 GB | ≤ 5 GiB per part |
| User metadata size | 2 KB (8 KB header total) | 8 KB |
| Bucket management ops | *Not formally documented* | 50 ops / s per bucket |
| Custom domains per bucket | Use S3 website/CloudFront (no fixed numeric limit) | 50 |
| Concurrent writes (same key) | *Not specified* | 1 write / s |

## Soft Limits S3 (Request‑Rate/Bandwidth)

### Bandwith 

> [Request‑rate and performance guidelines](https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html);

Amazon S3 enforces **soft request‑rate limits per prefix**, not a bytes‑per‑second cap.  
* **3 500 write‑type requests per second** (PUT, COPY, POST, DELETE) and **5 500 read‑type requests per second** (GET, HEAD) are accepted on each prefix.  
* When a workload temporarily exceeds that budget while S3 is still scaling, it returns **HTTP `503 Slow Down`** responses.  
* Scale higher by sharding objects across multiple prefixes (each gets its own budget) or by asking AWS Support to pre‑warm partitions.

## Soft Limits R2 (Request‑Rate/Bandwidth)

### Bandwith 

> [Public bucket rate‑limiting](https://developers.cloudflare.com/r2/platform/limits/#public-bucket-rate-limiting);

Cloudflare R2 advertises “zero‑cost egress” and publishes **no numeric request‑rate or bandwidth ceiling for production buckets** that use a custom domain.  
* The only documented throttle applies to the **`*.r2.dev` test endpoint**, which is rate‑limited at roughly “**hundreds of requests per second**” and may return **HTTP `429 Too Many Requests`** or slow transfers.  
* Cloudflare may apply anti‑abuse safeguards to abnormal spikes, but discloses no standard cap for production traffic.  
* Other limits—**50 bucket‑management operations per second** and **1 concurrent write per second to the same object key**—do not restrict read bandwidth.


### Free Egress 

Cloudflare pitches **R2** as *S3-compatible storage with zero egress fees*. We used this assumption in our back-of-the-napkin calculations. But every time the service that obviously costs something for the provider is free, we need to be sceptical about it. This note reviews the official fine print, user reports, and industry commentary that could be evidence of when “free” can still cost money or incur service limits. Moreover, our test where we are trying to face the limit.

#### Official Documents

1. [Marketing Page](https://www.cloudflare.com/en-gb/developer-platform/products/r2/): "No egress charges"
2. [R2 detailed pricing doc](https://developers.cloudflare.com/r2/pricing/): "Egress (data transfer to Internet) -- Free" (same table for Standard and Infrequent Access classes)
3. [R2 GA announcement (blog)](https://blog.cloudflare.com/r2-open-beta/?utm_source=chatgpt.com/): "Of course, there is no charge for egress bandwidth from R2. You can access your bucket to your heart's content."


#### Internet Research

1. [Reddit thread](https://www.reddit.com/r/CloudFlare/comments/1ic51x1/r2_pricing_serving_filesimages_is_not_free/)
   - A user running video workloads on Cloudflare R2 hit ~50 TB of cached traffic in 24 hours; Cloudflare support contacted them and required either disabling caching or switching to the paid Cloudflare Stream product.
   - One user moving 1–3 PB/month confirmed the same: the Enterprise negotiation felt opaque, and they wished Cloudflare published a clear usage cutoff instead of retroactively enforcing it.

2. [Storj Blog](https://www.storj.io/blog/is-free-egress-really-free)
   - Industry analysis argues that most "free egress" claims, including R2's, shift costs to other line items or rely on hidden quotas

3. [R2 Bandwidth limits, Cloudflare Community](https://community.cloudflare.com/t/r2-bandwidth-limits/395480/3) A staff reply confirms no egress fees but not-published hard cap; large users should open an enterprise ticket.

4. [HN thread on 300 PB example](https://news.ycombinator.com/item?id=33336053) Multiple responders state you won't be charged but may be contacted if usage is extreme.

5. [Reddit r/Cloudflare: R2 free egress restrictions?](https://www.reddit.com/r/CloudFlare/comments/193ibno/r2_free_egress_restrictions/?utm_source=chatgpt.com) Responders state you wonâ€™t be charged but may be contacted if usage is extreme.

##### Outcome  

* Cloudflare’s **May 16 2023 ToS update** deleted the old §2.8 “no-large-files” clause and explicitly allows video / large binaries when the origin is **R2, Stream, or Images**.  [oai_citation:6‡blog.cloudflare.com](https://blog.cloudflare.com/updated-tos/)  
* From mid-2023 through 2025, **no credible report shows R2 customers being billed for egress or forced to upgrade *because* of bandwidth**.  
* Practical limits today are:  
  * **Request-based costs** (Class A/B operations) — not bytes transferred.  
  * **`r2.dev` throttle** — stay on a custom domain for production.  
  * A generic “undue burden” clause Cloudflare can invoke for extreme traffic, though no post-2023 case is public.  

**Bottom line:** All recent evidence supports the conclusion that **R2’s “free egress” promise holds in real-world use**. Concerns you’ll find in older threads trace back to the now-retired §2.8 CDN rule or to using the dev endpoint, not to hidden bandwidth fees on R2 itself.

#### Testing framework

#### Testing Results




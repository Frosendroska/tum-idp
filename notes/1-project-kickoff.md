# Project Kickoff & Literature Review

> Research existing object storage solutions.\
Define evaluation criteria for comparing AWS S3 and Cloudflare R2.\
Identify key performance indicators (KPIs) such as latency, egress costs, and API compatibility.

## Overview
This phase focuses on understanding the current landscape of cloud object storage solutions, with particular emphasis on AWS S3 and Cloudflare R2.
The goal is to establish a solid foundation for subsequent analysis by identifying key characteristics, capabilities, and limitations of each solution. 
Here we skip the financial analysisю

## Table of Contents
1. [Block vs File vs Object Storage](#block-vs-file-vs-object-storage)
   1. [Definitions](#definitions)
   2. [Comparative Feature Matrix](#comparative-feature-matrix)
2. [Object-Storage Fundamentals](#object-storage-fundamentals)
   1. [Buckets & Objects](#buckets--objects)
   2. [Durability & Availability Guarantees](#durability--availability-guarantees)
   3. [Consistency Models](#consistency-models)
   4. [Metadata & Versioning](#metadata--versioning)
3. [Real-World Use Cases](#real-world-use-cases)
   1. [How It's Used In Practice](#how-its-used-in-practice)
   2. [CDN Origin & Static-Site Hosting](#cdn-origin--static-site-hosting)
   3. [Backup & Archival](#backup--archival)
   4. [Analytics / ML Pipelines](#analytics--ml-pipelines)
4. [Market Landscape](#market-landscape)
   1. [Hyperscale Providers](#hyperscale-providers)
   2. [Independent / Regional Clouds](#independent--regional-clouds)
   3. [Open-Source & Self-Hosted Solutions](#open-source--self-hosted-solutions)
5. [Evaluation Framework](#evaluation-framework)
   1. [Key Performance Indicators (KPIs)](#key-performance-indicators-kpis)
      1. [Latency & Throughput](#latency--throughput)
      2. [Consistency & Reliability](#consistency--reliability)
      3. [API Compatibility](#api-compatibility)
      4. [Data-Egress Cost](#data-egress-cost)
      5. [Security & Compliance](#security--compliance)
   2. [Qualitative Criteria](#qualitative-criteria)
   3. [Weighting & Scoring Method](#weighting--scoring-method)
6. [Deep Dive: Amazon S3](#deep-dive-amazon-s3)
   1. [Architecture Overview](#architecture-overview)
   2. [Feature Highlights](#feature-highlights)
   3. [Reference Use Cases](#reference-use-cases)
7. [Deep Dive: Cloudflare R2](#deep-dive-cloudflare-r2)
   1. [Architecture Overview](#architecture-overview-1)
   2. [Feature Highlights](#feature-highlights-1)
   3. [Reference Use Cases](#reference-use-cases-1)
8. [Architecture & Feature Comparison (S3 vs R2)](#architecture--feature-comparison-s3-vs-r2)
   1. [Side-by-Side Table](#side-by-side-table)
   2. [Narrative Analysis](#narrative-analysis)
9. [Benchmark & Validation Plan](#benchmark--validation-plan)
   1. [Test Matrix](#test-matrix)
   2. [Tooling & Environment](#tooling--environment)
   3. [Metrics Captured](#metrics-captured)
   4. [Reporting Format](#reporting-format)
10. [Migration Considerations](#migration-considerations)
    1. [Lift-and-Shift Approach](#lift-and-shift-approach)
    2. [Dual-Write / Cut-Over Strategy](#dual-write--cut-over-strategy)
    3. [API & Semantics Gaps](#api--semantics-gaps)
11. [Next Steps & Ownership](#next-steps--ownership)
    1. [Deliverables & Timeline](#deliverables--timeline)
    2. [Hand-offs & Responsibilities](#hand-offs--responsibilities)
    3. [Pointer to Cost-Model Page](#pointer-to-cost-model-page)

## Block vs File vs Object Storage

### Definitions

| Sources: [AWS Blog](https://aws.amazon.com/compare/the-difference-between-block-file-object-storage/)

🧱 **Block Storage** - Raw storage volumes split into fixed-size blocks. Requires a file system to manage data. Fast and low-latency, ideal for databases and VMs. Minimal built-in metadata.

**Example**: AWS EBS, Google Persistent Disk, local SSDs\

**Best for**: Databases, OS disks, low-latency apps

🗂️ **File Storage** - Hierarchical file and folder structure with standard protocols (NFS, SMB). Supports permissions and shared access. Best for traditional applications needing file paths.

**Example**: AWS EFS, Azure Files, Google Filestore, on-prem NAS\

**Best for**: Shared folders, file-based apps

🧺 **Object Storage** - Stores data as objects with rich metadata and unique IDs. Accessed via HTTP APIs. Highly scalable, great for unstructured data like images and backups.

**Example**: AWS S3, Cloudflare R2, Google Cloud Storage, Hetzner Storage Box\

**Best for**: Scalable storage for unstructured data

### Comparative Feature Matrix

| Feature              | Object Storage                                                                 | Block Storage                                                                              | Cloud File Storage                                                                     |
|----------------------|----------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| **File Management**   | Store files as objects. Access requires new code and APIs.                      | Can store files but needs extra budget and management to support file storage.             | Supports file-level protocols and permissions. Usable by existing applications.         |
| **Metadata Management** | Can store unlimited metadata and define custom fields.                         | Uses very little associated metadata.                                                      | Stores limited metadata relevant only to files.                                         |
| **Performance**       | Stores unlimited data with minimal latency.                                     | High-performance, low latency, and rapid data transfer.                                    | Offers high performance for shared file access.                                         |
| **Physical Storage**  | Distributed across multiple storage nodes.                                      | Distributed across SSDs and HDDs.                                                          | On-premises NAS servers or backed by block storage.                                     |
| **Scalability**       | Unlimited scale.                                                                 | Somewhat limited.                                                                          | Somewhat limited.                                                                       |

## Object-Storage Fundamentals

### Buckets & Objects

| Sources: [AWS Blog](https://aws.amazon.com/what-is/object-storage/), [CloudFlare Blog](https://www.cloudflare.com/en-
gb/learning/cloud/what-is-object-storage/)

Object storage is ideal for massive, scalable, reliable storage of data that's accessed in batches or over APIs.

Each object is stored in a flat structure and includes: 

- **Data** (e.g., an image, video, log file, Parquet file)
- **Unique identifier** (e.g., hash, UUID, ect)
- **Metadata** - optional or system defined (e.g., tags, timestamps, content type)

Each object is stored in a bucket.  

🪣 **Bucket** - container that holds objects — similar to a folder but without hierarchy. They help organize objects by project, user, application, or use case. Access permissions, region settings, and versioning policies can be applied at the bucket level.

1. Object storage is accessed via standard HTTP-based APIs.
2. Metadata plays crutial role for filtering, organizing, and classification of objects.
3. Object storage systems are built to be highly durable and scalable. Objects are stored across multiple servers or data 
centers using replication or erasure coding => fault tolerance, scalability, built-in versioning.
4. Designed for cost-Efficiency and massive scale. Object storage is typically low-cost and optimized for large volumes of 
unstructured data.
5. Access is done through an API.

### Durability & Availability Guarantees

TODO: Research and document durability and availability guarantees for major providers

### Consistency Models

TODO: Research and document consistency models (eventual vs strong) for major providers

### Metadata & Versioning

TODO: Research and document metadata capabilities and versioning features across providers

## Real-World Use Cases

### How It's Used In Practice

1. _Data Lake Storage_

   **Datalake** -  stores raw, unstructured or semi-structured data (like JSON, logs, images, Parquet) at large scale. It's flexible and schema-less, making it ideal for machine learning, exploratory analytics, and storing data in its original form.

   A data lake uses cloud object storage as its foundation because it has virtually unlimited scalability and high durability.

2. _ETL/ELT Pipelines_

   **ETL (Extract, Transform, Load) and ELT (Extract, Load, Transform)** - data processing workflows used to move data from source systems to move data.

   Object storage is often used as a staging or intermediate layer in ETL/ELT pipelines.

3. _Data Sharing & Interchange_

   Companies and individuals use object storage to share data across teams, regions, or even companies.

4. _Machine Learning & Analytics_

   Machine learning requires object storage because of the scale and cost efficiency. ML teams use object storages for training data, model weights and logs.

5. _Cloud Apps: Static Assets & CDN Origins_

    Web apps use object storage for hosting static websites (HTML/CSS/JS), serving user uploads (images, docs, videos), origin storage for CDNs (Cloudflare, AWS CloudFront).

6. _Backups, Snapshots, Archival_

   Cloud object storage is excellent for long-term data retention. It is cheap, has long retention and immutable by default.

### CDN Origin & Static-Site Hosting

TODO: Research and document CDN integration patterns and static site hosting capabilities

### Backup & Archival

TODO: Research and document backup and archival features, including lifecycle policies and storage tiers

### Analytics / ML Pipelines

TODO: Research and document analytics and ML pipeline integration patterns

## Market Landscape

### Hyperscale Providers

| Provider         | Service Name              | Notes                                                                 |
|------------------|---------------------------|-----------------------------------------------------------------------|
| Amazon           | S3 (Simple Storage Service) | **Industry standard**, highly durable and scalable                 |
| Google Cloud     | Cloud Storage             | S3-like service, tightly integrated with Google's data & AI tools    |
| Microsoft Azure  | Blob Storage              | Supports hot/cool/archive tiers, integrates with Azure Data Lake     |

![image](https://github.com/user-attachments/assets/c3d2259e-850f-4d56-b92e-44fa7a8c7826)

### Independent / Regional Clouds

TODO: Research and document independent and regional cloud providers

### Open-Source & Self-Hosted Solutions

TODO: Research and document open-source and self-hosted solutions

## Evaluation Framework

### Key Performance Indicators (KPIs)

#### Latency & Throughput

TODO: Define latency and throughput KPIs and measurement methodology

#### Consistency & Reliability

TODO: Define consistency and reliability KPIs and measurement methodology

#### API Compatibility

TODO: Define API compatibility KPIs and measurement methodology

#### Data-Egress Cost

TODO: Document data egress cost comparison methodology

#### Security & Compliance

TODO: Define security and compliance KPIs and measurement methodology

### Qualitative Criteria

TODO: Define qualitative evaluation criteria

### Weighting & Scoring Method

TODO: Define weighting and scoring methodology

## Deep Dive: Amazon S3

- 🥇 _First mover_: Launched in 2006, pioneered cloud object storage.
- 🌐 _S3 API became universal_: Most tools and services support it natively.
- ♻️ _Ecosystem integration_: Deeply connected to AWS (Lambda, CloudFront, Athena, etc.).
- 🌍 _Global scale_: Backed by Amazon's massive infrastructure.
- 🫂 _Enterprise trust_: Proven durability, security, and compliance over decades.

### Architecture Overview

 ![image](https://github.com/user-attachments/assets/c3d2259e-850f-4d56-b92e-44fa7a8c7826)

- 🛢️ Storage Model
  - Data is stored as objects inside buckets.
  - Each object includes:
    - The data itself (binary blob)
    - Metadata (system and user-defined)
    - A unique key (object name)

- 🏗️ Physical Storage
  - Objects are automatically replicated across multiple Availability Zones (AZs) within a region.
  - This replication ensures **11 nines (99.999999999%) durability**.
  - Storage hardware is abstracted — users never deal directly with disks or servers.

- 🗺️ Namespace and Structure
  - S3 uses a **flat namespace** — "folders" are simulated using object key prefixes (e.g., `photos/2025/04/image.jpg`).
  - There is no real hierarchy like in a traditional file system.


### Feature Highlights

- 🌐 Access Layer (API)
  - Users and services access objects via the **S3 REST API** or **AWS SDKs**.
  - Supports operations like:
    - `GET`
    - `PUT`
    - `DELETE`
    - `LIST`
    - `COPY`
  - APIs are designed for high concurrency and **strong consistency** (available after the 2020 update).

- 🧩 Service Integration
  - S3 integrates natively with many AWS services:
    - CloudFront (CDN delivery)
    - Lambda (serverless processing)
    - Athena (SQL over S3)
    - Redshift Spectrum (external tables)
    - EventBridge and SNS (event-driven actions)

- 🔐 Security
  - Supports:
    - Bucket policies
    - IAM roles/policies
    - Access control lists (ACLs)
    - Object ownership settings
  - Encryption options:
    - **Server-Side Encryption with S3 Managed Keys (SSE-S3)**
    - **Server-Side Encryption with KMS Managed Keys (SSE-KMS)**
    - **Client-Side Encryption**

- 🏎️ Performance Features
  - **Multi-part upload** for large objects.
  - **Byte-range retrieval** for partial downloads.
  - **Transfer Acceleration** for faster uploads via CloudFront edge locations.
  - **Intelligent-Tiering** to automatically move data to cheaper storage classes based on access patterns.

### Reference Use Cases

1. ❄️ _Snowflake_
  
   Source: [SIGMOD 2016 "The Snowflake Elastic Data Warehouse"](https://info.snowflake.net/rs/252-RFO-227/images/Snowflake_SIGMOD.pdf)  

   Under the covers, Snowflake stores its data in AWS S3. When you spin up a Snowflake "virtual warehouse," it will pull data from S3 into its own compute/cache tier and then scale compute independently of the storage layer. They proceeded with S3, because it's usability, high availability, and strong durability guarantees are hard to beat.
  
2. 🧱 _DataBricks_

   Source: [DataBricks Website](https://www.databricks.com/blog/multi-cloud-architecture-portable-data-and-ai-processing-financial-services)

   S3 is used as the default data lake backend for Delta Lake tables. Spark clusters pull data from S3, transform, and write back.

3. 📺 _Netflix_

   Source: [Re:Invent 2020](https://aws.amazon.com/solutions/case-studies/netflix-storage-reinvent22/)

   Netflix employs a microservices architecture hosted on AWS, with Amazon S3 serving as the central storage for media assets, logs, and analytics data.

4. 🏠 _AirBNB_
  
   Source: [Amazon Website](https://aws.amazon.com/solutions/case-studies/airbnb-optimizes-usage-and-costs-case-study/)

   Airbnb's data infrastructure leverages Amazon S3 as the primary data lake, storing logs, images, and analytical data.

5. 🖼️ _Pinterest_

   Source: [Amazon Website](https://aws.amazon.com/solutions/case-studies/innovators/pinterest/)
  
   Pinterest's platform relies heavily on Amazon S3 to store user-generated content, such as images and videos.

6. 💭 _Salesforce_

   Source: [Amazon Website](https://aws.amazon.com/solutions/case-studies/innovators/salesforce/#:~:text=Salesforce%20launched%20Hyperforce%20on%20AWS,residency%20and%20data%20sovereignty%20regulations.)
  
   Salesforce utilizes Amazon S3 to store backups, logs, and static assets across various services.
   
---

## Deep Dive: Cloudflare R2

Sources: [Cloudflare R2 documentation](https://developers.cloudflare.com/r2/), [Cloudflare R2 website](https://www.cloudflare.com/en-gb/developer-platform/products/r2/?utm_source=chatgpt.com)

### Why is R2 a Disruptive Alternative to S3?

Source: [Medium](https://y-consulting.medium.com/cloudflare-r2-vs-the-big-3-a-deep-dive-into-cost-and-technical-efficiency-of-cloud-storage-c1644c61a0d3)

- 🚫 **Zero Egress Fees**: Unlike traditional cloud providers, Cloudflare R2 eliminates data transfer (egress) fees, making it highly cost-effective for data-intensive applications.
- 🔄 **S3-Compatible API**: R2 supports the S3 API, facilitating seamless migration and integration with existing tools and workflows.
- 🌐 **Global Edge Network**: Leveraging Cloudflare's extensive global network, R2 ensures low-latency data access worldwide.  ￼
- 🧩 **Integrated Ecosystem**: R2 integrates natively with Cloudflare Workers, enabling serverless compute operations directly on stored data.  ￼
- 📊 **Predictable Pricing**: With transparent and straightforward pricing, R2 offers a cost-effective solution without hidden fees.  ￼

### Architecture Overview

- 🛢️ **Storage Model**:
  - Data is stored as **objects** inside **buckets**.
  - Each object contains the data, metadata, and a unique key (object name).
  - Fully S3 API-compatible, making migration from S3 seamless.

- 🏗️ **Physical Storage**:
  - Distributed across **Cloudflare's global network of edge data centers**.
  - Optimized for low-latency access but centralized for consistency — not full replication at every edge.
  - Designed to minimize cost by eliminating traditional region-based storage complexity.

- 🗺️ **Namespace and Structure**:
  - Uses a **flat namespace** like S3 (no true folders, only key prefixes).
  - Public and private buckets supported.
  - Easy integration with access control and versioning features.

### Feature Highlights

- 🌐 **Access Layer (API)**:
  - Provides a **fully S3-compatible API**.
  - Supports standard operations like `PUT`, `GET`, `DELETE`, `LIST`.
  - Integrates with Cloudflare Workers for serverless compute close to storage.

- 🧩 **Service Integration**:
  - Tight integration with **Cloudflare Workers** for in-flight data processing.
  - Works naturally with **Cloudflare Stream**, **Pages**, and **Zero Trust** for secure delivery.
  - Can serve content directly via **Cloudflare CDN** without egress fees.

- 🔐 **Security**:
  - Fine-grained bucket policies and object permissions.
  - Supports **signed URLs** for temporary public access.
  - Integrated with Cloudflare's global security services (WAF, DDoS protection).

- 🏎️ **Performance Features**:
  - **Edge-based caching** available automatically when serving objects through Cloudflare CDN.
  - **No egress fees** makes direct delivery to users cheap and scalable.
  - Event-driven architecture supported (object creation triggers via Workers).

### Reference Use Cases

1. 📈 **LunarCrush**

     Source: [R2 website](https://workers.cloudflare.com/built-with/projects/lunarcrush)

     Utilizes R2 to scale globally without worrying about traffic surges, infrastructure limits, or surprise egress costs.  ￼

     > "No egress fees is a big advantage, as surprise costs from surging traffic can be annoying. As a startup, one has to be careful about surging costs for DDoS or viral traffic, but with Cloudflare, these worries are eliminated. Thanks to Cloudflare, startups don't need to scale up dramatically or set up their own servers. This results in significant cost savings and eliminates the need for their own infrastructure."
   
3. 🎨 **Canva** 

     Sources: [Canva website](https://canvaplugin.com/how-to-connect-canva-to-cloudflare/#:~:text=Canva's%20partnership%20with%20Cloudflare%20began,serverless%20development%2C%20and%20bot%20management.), [R2 website](https://www.cloudflare.com/en-gb/developer-platform/products/r2/)

    Chose R2 for faster, more secure hosting with free DDoS protection, CDN performance, and serverless development.

5. 🍕 **DeliveryHero**

     Source: [R2 website](https://www.cloudflare.com/en-gb/case-studies/delivery-hero/)

     Leverages R2 to simplify security for remote work, protect against cyberattacks, and handle global traffic surges efficiently across its public apps and internal systems.

## Architecture & Feature Comparison (S3 vs R2)

### Side-by-Side Table

| Aspect                | Amazon S3                                         | Cloudflare R2                                     |
|------------------------|--------------------------------------------------|--------------------------------------------------|
| 🛢️ Storage Model       | Centralized per-region object storage.            | Globalized object storage via Cloudflare's edge network. |
|                        | Data is stored in AWS regions (e.g., us-east-1). | Data is accessible globally, but still primarily stored centrally. |
|                        | Explicit region selection during bucket creation.| No need to pick a region — Cloudflare handles routing. |
| 🏗️ Physical Storage     | Replicates data across multiple AZs inside a region.| Centralized storage locations, optimized for low egress and fast CDN serving. |
| 🗺️ Namespace Structure  | Flat namespace; folders simulated with prefixes. | Flat namespace; folders simulated with prefixes. |
| 🌐 API Access           | S3 REST API, AWS SDKs.                            | Fully S3-compatible API (can reuse existing S3 code). |
| 🧩 Service Integration  | Deep integration with AWS services (Lambda, Athena, Redshift, etc.). | Deep integration with Cloudflare Workers, CDN, Pages, and Stream. |
| 🔐 Security             | IAM policies, ACLs, bucket policies, encryption options (SSE-S3, SSE-KMS). | Bucket-level permissions, signed URLs, integrated DDoS/WAF protection. |
| 🏎️ Performance Features | Multi-part uploads, byte-range retrievals, Transfer Acceleration. | Edge caching via CDN, event-driven triggers via Workers. |
| 💵 Egress Cost          | Egress to Internet is expensive ($0.09/GB for first 10TB). | No egress cost to Internet — **free egress**. |
| 💬 Other Notes          | Massive ecosystem, enterprise support, strong consistency model.| Great for cost-saving at scale, especially for public-facing workloads. |

### Narrative Analysis

TODO: Add narrative analysis comparing S3 and R2

## Benchmark & Validation Plan

### Test Matrix

TODO: Define test matrix including object sizes and regions

### Tooling & Environment

TODO: Define tooling and environment setup

### Metrics Captured

TODO: Define metrics to be captured during testing

### Reporting Format

TODO: Define reporting format and structure

## Migration Considerations

### Lift-and-Shift Approach

TODO: Document lift-and-shift migration approach

### Dual-Write / Cut-Over Strategy

TODO: Document dual-write and cut-over strategies

### API & Semantics Gaps

TODO: Document API and semantics gaps between providers

## Next Steps & Ownership

### Deliverables & Timeline

TODO: Define deliverables and timeline

### Hand-offs & Responsibilities

TODO: Define hand-offs and responsibilities

### Pointer to Cost-Model Page

TODO: Add pointer to cost-model page
# Project Kickoff & Literature Review

> Research existing object storage solutions and cost structures.\
Define evaluation criteria for comparing AWS S3 and Cloudflare R2.\
Identify key performance indicators (KPIs) such as latency, egress costs, and API compatibility.

## Overview
This phase focuses on understanding the current landscape of cloud object storage solutions, with particular emphasis on AWS S3 and Cloudflare R2. The goal is to establish a solid foundation for subsequent analysis by identifying key characteristics, capabilities, and limitations of each solution.

## Table of Contents
1. [Block vs File vs Object Storage](#block-vs-file-vs-object-storage)
2. [Object Storage Fundamentals](#object-storages)
3. [Use Cases in Practice](#how-its-used-in-practice)
4. [Market Solutions Overview](#solutions-in-the-market)
5. [Amazon S3 Deep Dive](#amazon-s3)
   - [Why S3 is Industry Standard](#why-is-s3-an-industry-standard-solution)
   - [S3 Architecture](#s3-architecture)
   - [Companies Using S3](#companies-that-use-s3)
6. [Cloudflare R2 Deep Dive](#cloudflare-r2)
   - [Why R2 is Disruptive](#why-is-r2-a-disruptive-alternative-to-s3)
   - [R2 Architecture](#r2-architecture)
   - [Companies Using R2](#companies-that-use-r2)
7. [Architecture Comparison](#s3-vs-r2--architecture-comparison)

## Block vs File vs Object storage

Sources: [AWS Blog](https://aws.amazon.com/compare/the-difference-between-block-file-object-storage/)

🧱 **Block Storage** - Raw storage volumes split into fixed-size blocks. Requires a file system to manage data. Fast and low-latency, ideal for databases and VMs. Minimal built-in metadata.

**Example**: AWS EBS, Google Persistent Disk, local SSDs\

**Best for**: Databases, OS disks, low-latency apps

🗂️ **File Storage** - Hierarchical file and folder structure with standard protocols (NFS, SMB). Supports permissions and shared access. Best for traditional applications needing file paths.

**Example**: AWS EFS, Azure Files, Google Filestore, on-prem NAS\

**Best for**: Shared folders, file-based apps

🧺 **Object Storage** - Stores data as objects with rich metadata and unique IDs. Accessed via HTTP APIs. Highly scalable, great for unstructured data like images and backups.

**Example**: AWS S3, Cloudflare R2, Google Cloud Storage, Hetzner Storage Box\

**Best for**: Scalable storage for unstructured data


| Feature              | Object Storage                                                                 | Block Storage                                                                              | Cloud File Storage                                                                     |
|----------------------|----------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| **File Management**   | Store files as objects. Access requires new code and APIs.                      | Can store files but needs extra budget and management to support file storage.             | Supports file-level protocols and permissions. Usable by existing applications.         |
| **Metadata Management** | Can store unlimited metadata and define custom fields.                         | Uses very little associated metadata.                                                      | Stores limited metadata relevant only to files.                                         |
| **Performance**       | Stores unlimited data with minimal latency.                                     | High-performance, low latency, and rapid data transfer.                                    | Offers high performance for shared file access.                                         |
| **Physical Storage**  | Distributed across multiple storage nodes.                                      | Distributed across SSDs and HDDs.                                                          | On-premises NAS servers or backed by block storage.                                     |
| **Scalability**       | Unlimited scale.                                                                 | Somewhat limited.                                                                          | Somewhat limited.                                                                       |

## Object Storages

Sources: [AWS Blog](https://aws.amazon.com/what-is/object-storage/), [CloudFlare Blog](https://www.cloudflare.com/en-gb/learning/cloud/what-is-object-storage/)

Object storage is ideal for massive, scalable, reliable storage of data that's accessed in batches or over APIs.

Each object is stored in a flat structure and includes: 

- **Data** (e.g., an image, video, log file, Parquet file)
- **Unique identifier** (e.g., hash, UUID, ect)
- **Metadata** - optional or system defined (e.g., tags, timestamps, content type)

Each object is stored in a bucket.  

🪣 **Bucket** - container that holds objects — similar to a folder but without hierarchy. They help organize objects by project, user, application, or use case. Access permissions, region settings, and versioning policies can be applied at the bucket level.

1. Object storage is accessed via standard HTTP-based APIs.
2. Metadata plays crutial role for filtering, organizing, and classification of objects.
3. Object storage systems are built to be highly durable and scalable. Objects are stored across multiple servers or data centers using replication or erasure coding => fault tolerance, scalability, built-in versioning.
4. Designed for cost-Efficiency and massive scale. Object storage is typically low-cost and optimized for large volumes of unstructured data.
5. Access is done through an API.

## How It's Used in Practice

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

## Solutions in the market

| Provider         | Service Name              | Notes                                                                 |
|------------------|---------------------------|-----------------------------------------------------------------------|
| Amazon           | S3 (Simple Storage Service) | **Industry standard**, highly durable and scalable                 |
| Google Cloud     | Cloud Storage             | S3-like service, tightly integrated with Google's data & AI tools    |
| Microsoft Azure  | Blob Storage              | Supports hot/cool/archive tiers, integrates with Azure Data Lake     |
| IBM              | Cloud Object Storage      | Hybrid/cloud solution based on Cleversafe technology                 |
| Cloudflare       | R2                        | S3-compatible, **no egress fees**, great for CDN-origin use cases    |
| Backblaze        | B2 Cloud Storage          | Cost-effective, S3-compatible, used for backups and archives         |
| Wasabi           | Hot Cloud Storage         | Flat pricing, no egress or API fees, S3-compatible                   |
| Hetzner          | Object Storage            | EU-based, affordable, S3-compatible                                  |
| DigitalOcean     | Spaces                    | Simple S3-compatible storage for web apps and static sites           |
| Scaleway         | Object Storage            | French provider, S3-compatible, supports lifecycle rules             |
| MinIO            | MinIO (self-hosted)       | Lightweight open-source S3-compatible, ideal for private deployments |
| Ceph             | Ceph Object Gateway (RGW) | Scalable open-source storage, supports object, file, and block       |
| OpenIO           | OpenIO Object Storage     | Acquired by OVH, flexible and open source                            |
| SeaweedFS        | SeaweedFS                 | Efficient file + object hybrid storage, lightweight and fast         |

    NOTE: Wasabi also has no egress fees: https://wasabi.com/cloud-object-storage. The data is stored in Wasabi's own servers inside top-tier colocation facilities.

---

## Amazon S3

### Why is S3 an industry-standard solution?

- 🥇 _First mover_: Launched in 2006, pioneered cloud object storage.
- 🌐 _S3 API became universal_: Most tools and services support it natively.
- ♻️ _Ecosystem integration_: Deeply connected to AWS (Lambda, CloudFront, Athena, etc.).
- 🌍 _Global scale_: Backed by Amazon's massive infrastructure.
- 🫂 _Enterprise trust_: Proven durability, security, and compliance over decades.

### S3 Architecture

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

### Companies That Use S3

A lot of companies leverage S3 under the hood of their architectures. 

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

## Cloudflare R2

Cloudflare R2 presents a compelling alternative to traditional object storage solutions, particularly for applications with high data transfer requirements. Its integration with Cloudflare's global network and serverless compute platform offers developers a powerful and cost-effective storage solution.

Sources: [Cloudflare R2 documentation](https://developers.cloudflare.com/r2/), [Cloudflare R2 website](https://www.cloudflare.com/en-gb/developer-platform/products/r2/?utm_source=chatgpt.com)

### Why is R2 a Disruptive Alternative to S3?

Source: [Medium](https://y-consulting.medium.com/cloudflare-r2-vs-the-big-3-a-deep-dive-into-cost-and-technical-efficiency-of-cloud-storage-c1644c61a0d3)

- 🚫 **Zero Egress Fees**: Unlike traditional cloud providers, Cloudflare R2 eliminates data transfer (egress) fees, making it highly cost-effective for data-intensive applications.
- 🔄 **S3-Compatible API**: R2 supports the S3 API, facilitating seamless migration and integration with existing tools and workflows.
- 🌐 **Global Edge Network**: Leveraging Cloudflare's extensive global network, R2 ensures low-latency data access worldwide.  ￼
- 🧩 **Integrated Ecosystem**: R2 integrates natively with Cloudflare Workers, enabling serverless compute operations directly on stored data.  ￼
- 📊 **Predictable Pricing**: With transparent and straightforward pricing, R2 offers a cost-effective solution without hidden fees.  ￼

### R2 Architecture

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


### Companies That Use R2

Several organizations leverage Cloudflare R2 for its performance and cost benefits:

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

## S3 vs R2 — Architecture Comparison

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
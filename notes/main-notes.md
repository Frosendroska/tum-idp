# Project Kickoff & Literature Review

> Research existing object storage solutions and cost structures.\
Define evaluation criteria for comparing AWS S3 and Cloudflare R2.\
Identify key performance indicators (KPIs) such as latency, egress costs, and API compatibility.

## Block vs File vs Object storage

Sources: [AWS Blog](https://aws.amazon.com/compare/the-difference-between-block-file-object-storage/)

🧱 **Block Storage** - Raw storage volumes split into fixed-size blocks. Requires a file system to manage data. Fast and low-latency, ideal for databases and VMs. Minimal built-in metadata.

> Example: AWS EBS, Google Persistent Disk, local SSDs\
Best for: Databases, OS disks, low-latency apps

🗂️ **File Storage** - Hierarchical file and folder structure with standard protocols (NFS, SMB). Supports permissions and shared access. Best for traditional applications needing file paths.

> Example: AWS EFS, Azure Files, Google Filestore, on-prem NAS\
Best for: Shared folders, file-based apps

🧺 **Object Storage** - Stores data as objects with rich metadata and unique IDs. Accessed via HTTP APIs. Highly scalable, great for unstructured data like images and backups.

> Example: AWS S3, Cloudflare R2, Google Cloud Storage, Hetzner Storage Box\
Best for: Scalable storage for unstructured data


| Feature              | Object Storage                                                                 | Block Storage                                                                              | Cloud File Storage                                                                     |
|----------------------|----------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| **File Management**   | Store files as objects. Access requires new code and APIs.                      | Can store files but needs extra budget and management to support file storage.             | Supports file-level protocols and permissions. Usable by existing applications.         |
| **Metadata Management** | Can store unlimited metadata and define custom fields.                         | Uses very little associated metadata.                                                      | Stores limited metadata relevant only to files.                                         |
| **Performance**       | Stores unlimited data with minimal latency.                                     | High-performance, low latency, and rapid data transfer.                                    | Offers high performance for shared file access.                                         |
| **Physical Storage**  | Distributed across multiple storage nodes.                                      | Distributed across SSDs and HDDs.                                                          | On-premises NAS servers or backed by block storage.                                     |
| **Scalability**       | Unlimited scale.                                                                 | Somewhat limited.                                                                          | Somewhat limited.                                                                       |

## Object Storages

Sources: [AWS Blog](https://aws.amazon.com/what-is/object-storage/), [CloudFlare Blog](https://www.cloudflare.com/en-gb/learning/cloud/what-is-object-storage/)

Object storage is ideal for massive, scalable, reliable storage of data that’s accessed in batches or over APIs.

Each object is stored in a flat structure and includes: 

- **Data** (e.g., an image, video, log file, Parquet file)
- **Unique identifier** (e.g., hash, UUID, ect)
- **Metadata** - optional or system defined (e.g., tags, timestamps, content type)

Each object is stored in a bucket.  

🪣 **Bucket** - container that holds objects — similar to a folder but without hierarchy. They help organize objects by project, user, application, or use case. Access permissions, region settings, and versioning policies can be applied at the bucket level.

1. Object storage is accessed via standard HTTP-based APIs.
2. Metadata plays crutial role for filtering, organazing and classification of objects.
3. Object storage systems are built to be highly durable and scalable. Objects are stored across multiple servers or data centers using replication or erasure coding => fault tolerance, scalability, build-in versioning.
4. Designed for cost-Efficiency and massive scale. Object storage is typically low-cost and optimized for large volumes of unstructured data.
5. Access is done through an API.

### How It’s Used in Practice

1. _Data Lake Storage_

   **Datalake** -  stores raw, unstructured or semi-structured data (like JSON, logs, images, Parquet) at large scale. It’s flexible and schema-less, making it ideal for machine learning, exploratory analytics, and storing data in its original form.

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

### Solutions in the market

| Provider         | Service Name              | Notes                                                                 |
|------------------|---------------------------|-----------------------------------------------------------------------|
| Amazon           | S3 (Simple Storage Service) | **Industry standard**, highly durable and scalable                 |
| Google Cloud     | Cloud Storage             | S3-like service, tightly integrated with Google’s data & AI tools    |
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
    
### Why S3 is an industry standard solution?

- _First mover_: Launched in 2006, pioneered cloud object storage.
- _S3 API became universal_: Most tools and services support it natively.
- _Ecosystem integration_: Deeply connected to AWS (Lambda, CloudFront, Athena, etc.).
- _Global scale_: Backed by Amazon’s massive infrastructure.
- _Enterprise trust_: Proven durability, security, and compliance over decades.

### S3 Architecture

### Big Cloud-Native Companies That Use S3

A lot of companies leverage S3 under the hood of their architectures. 

1. ❄️ _Snowflake_
  
   Source: [SIGMOD 2016 "The Snowflake Elastic Data Warehouse"](https://info.snowflake.net/rs/252-RFO-227/images/Snowflake_SIGMOD.pdf)  

   Under the covers, Snowflake stores its data in AWS S3. When you spin up a Snowflake “virtual warehouse,” it will pull data from S3 into its own compute/cache tier and then scale compute independently of the storage layer. They proceeded with S3, because it's usability, high availability, and strong durability guarantees are hard to beat.
  
2. 🧱 _DataBricks_

   Source: [DataBricks Website](https://www.databricks.com/blog/multi-cloud-architecture-portable-data-and-ai-processing-financial-services)

   S3 is used as the default data lake backend for Delta Lake tables. Spark clusters pull data from S3, transform, and write back.

3. 📺 _Netflix_

   Source: [Re:Invent 2020](https://aws.amazon.com/solutions/case-studies/netflix-storage-reinvent22/)

   Netflix employs a microservices architecture hosted on AWS, with Amazon S3 serving as the central storage for media assets, logs, and analytics data.

4. 🏠 _AirBNB_
  
   Source: [Amazon Website](https://aws.amazon.com/solutions/case-studies/airbnb-optimizes-usage-and-costs-case-study/)

   Airbnb’s data infrastructure leverages Amazon S3 as the primary data lake, storing logs, images, and analytical data.

5. 🖼️ _Pinterest_

   Source: [Amazon Website](https://aws.amazon.com/solutions/case-studies/innovators/pinterest/)
  
   Pinterest’s platform relies heavily on Amazon S3 for storing user-generated content, such as images and videos.

6. 💭 _Salesforce_

   Source: [Amazon Website](https://aws.amazon.com/solutions/case-studies/innovators/salesforce/#:~:text=Salesforce%20launched%20Hyperforce%20on%20AWS,residency%20and%20data%20sovereignty%20regulations.)
  
  Salesforce utilizes Amazon S3 for storing backups, logs, and static assets across various services.

### Amazon S3 Storage Pricing (April 2025)

Source: [AWS S3 Pricing page](https://aws.amazon.com/s3/pricing/)

| Storage Class                         | Tier / Description                                         | Price                    |
|--------------------------------------|------------------------------------------------------------|--------------------------|
| **S3 Standard**                      | First 50 TB / Month                                        | $0.023 per GB            |
|                                      | Next 450 TB / Month                                        | $0.022 per GB            |
|                                      | Over 500 TB / Month                                        | $0.021 per GB            |
| **S3 Intelligent-Tiering***          | Monitoring & Automation (Objects > 128 KB)                 | $0.0025 per 1,000 objects|
|                                      | Frequent Access Tier, First 50 TB / Month                  | $0.023 per GB            |
|                                      | Frequent Access Tier, Next 450 TB / Month                  | $0.022 per GB            |
|                                      | Frequent Access Tier, Over 500 TB / Month                  | $0.021 per GB            |
|                                      | Infrequent Access Tier                                     | $0.0125 per GB           |
|                                      | Archive Instant Access Tier                                | $0.004 per GB            |
| **S3 Intelligent-Tiering (Archive)** | Archive Access Tier                                        | $0.0036 per GB           |
|                                      | Deep Archive Access Tier                                   | $0.00099 per GB          |
| **S3 Standard-IA** **                | All Storage / Month                                        | $0.0125 per GB           |
| **S3 Express One Zone**              | All Storage / Month                                        | $0.11 per GB             |
| **S3 Glacier Instant Retrieval***    | All Storage / Month                                        | $0.004 per GB            |
| **S3 Glacier Flexible Retrieval***   | All Storage / Month                                        | $0.0036 per GB           |
| **S3 Glacier Deep Archive***         | All Storage / Month                                        | $0.00099 per GB          |
| **S3 One Zone-IA** **                | All Storage / Month                                        | $0.01 per GB             |

---

**Notes**:
- \* Intelligent-Tiering includes automatic cost optimization based on access patterns.
- \** "IA" = Infrequent Access – designed for long-lived, less frequently accessed data.
- \*** Glacier classes are suitable for archival and backup use cases with varying retrieval speeds.


### Amazon S3 data transfer pricing (April 2025)

Source: [AWS S3 Pricing page](https://aws.amazon.com/s3/pricing/)

 **Egress** - In networking terminology, egress refers to outbound data transfer from a network to another network or an individual server. For cloud providers, this means data that is transferred from one cloud provider’s data centers to the public internet, another cloud provider, or to your own infrastructure.
 

Charges apply in the following scenarios:
 
- Data transferred **OUT From Amazon S3 To Internet**.
  First 10 TB / Month	$0.09 per GB
  Next 40 TB / Month	$0.085 per GB
  Next 100 TB / Month	$0.07 per GB
  Greater than 150 TB / Month	$0.05 per GB
  
- Data transferred **from S3 to AWS services in a different region**: For example, accessing S3 data from an EC2 instance in another region.
  From $0.01 per GB to $0.08 per GB

Data transfers are free in these cases:

- Data transferred **out to the internet** for the first 100GB per month, aggregated across all AWS Services and Regions (except China and GovCloud)
- Data transferred **in from the internet**.
- Data transferred **from an Amazon S3 bucket to any AWS service(s) within the same AWS Region as the S3 bucket** (including to a different account in the same AWS Region).
 

# Financial Analysis

# Implementation of Performance Tests & Monitoring

# Technical Benchmarking

# Documentation & Presentation Preparation

# Financial Analysis

## Overview
This phase focuses on conducting a comprehensive financial analysis of AWS S3 and Cloudflare R2, with particular attention to total cost of ownership (TCO) and potential cost savings. The analysis will consider various real-world scenarios and integration patterns with major cloud providers.


## Table of Contents
- [Financial Analysis](#financial-analysis)
  - [Overview](#overview)
  - [Table of Contents](#table-of-contents)
  - [Amazon S3 Pricing (April 2025)](#amazon-s3-pricing-april-2025)
    - [Storage Pricing](#storage-pricing)
    - [Operations Pricing](#operations-pricing)
    - [Data Transfer Pricing](#data-transfer-pricing)
  - [Cloudflare R2 Pricing (April 2025)](#cloudflare-r2-pricing-april-2025)
    - [Storage Pricing](#storage-pricing-1)
    - [Operations Pricing](#operations-pricing-1)
  - [S3 vs R2 — Pricing Comparison (April 2025)](#s3-vs-r2--pricing-comparison-april-2025)


## Amazon S3 Pricing (April 2025)

> Source: [AWS S3 Pricing page](https://aws.amazon.com/s3/pricing/)

### Storage Pricing

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

### Operations Pricing

| Storage Class                         | PUT, COPY, POST, LIST (per 1,000 requests) | GET, SELECT, Other (per 1,000 requests) | Lifecycle Transition (per 1,000 requests) | Data Retrieval Requests (per 1,000 requests) | Data Uploads (per GB) | Data Retrievals (per GB) |
|----------------------------------------|--------------------------------------------|-----------------------------------------|--------------------------------------------|-----------------------------------------------|------------------------|---------------------------|
| **S3 Standard**                       | $0.005                                     | $0.0004                                 | n/a                                        | n/a                                           | n/a                    | n/a                       |
| **S3 Intelligent-Tiering** *           | $0.005                                     | $0.0004                                 | $0.01                                      | n/a                                           | n/a                    | n/a                       |
| Frequent Access                       | n/a                                        | n/a                                     | n/a                                        | n/a                                           | n/a                    | n/a                       |
| Infrequent Access                     | n/a                                        | n/a                                     | n/a                                        | n/a                                           | n/a                    | n/a                       |
| Archive Instant                       | n/a                                        | n/a                                     | n/a                                        | n/a                                           | n/a                    | n/a                       |
| Archive Access, Standard              | n/a                                        | n/a                                     | n/a                                        | n/a                                           | n/a                    | n/a                       |
| Archive Access, Bulk                  | n/a                                        | n/a                                     | n/a                                        | n/a                                           | n/a                    | n/a                       |
| Archive Access, Expedited             | n/a                                        | n/a                                     | n/a                                        | $10.00                                        | n/a                    | $0.03                     |
| Deep Archive Access, Standard         | n/a                                        | n/a                                     | n/a                                        | n/a                                           | n/a                    | n/a                       |
| Deep Archive Access, Bulk             | n/a                                        | n/a                                     | n/a                                        | n/a                                           | n/a                    | n/a                       |
| **S3 Standard-Infrequent Access** **   | $0.01                                      | $0.001                                  | $0.01                                      | n/a                                           | n/a                    | $0.01                     |
| **S3 Express One Zone**                | $0.00113                                   | $0.00003                                | n/a                                        | n/a                                           | $0.0032                | $0.0006                   |
| **S3 Glacier Instant Retrieval** ***   | $0.02                                      | $0.01                                   | $0.02                                      | n/a                                           | n/a                    | $0.03                     |
| **S3 Glacier Flexible Retrieval** ***  | $0.03                                      | $0.0004                                 | $0.03                                      | See below                                    | n/a                    | See below                 |
| Expedited                             | n/a                                        | n/a                                     | n/a                                        | $10.00                                        | n/a                    | $0.03                     |
| Standard                              | n/a                                        | n/a                                     | n/a                                        | $0.05                                         | n/a                    | $0.01                     |
| Bulk ***                              | n/a                                        | n/a                                     | n/a                                        | n/a                                           | n/a                    | n/a                       |
| Provisioned Capacity Unit ****        | n/a                                        | n/a                                     | n/a                                        | n/a                                           | n/a                    | $100.00 per unit          |
| **S3 Glacier Deep Archive** ***        | $0.05                                      | $0.0004                                 | $0.05                                      | See below                                    | n/a                    | See below                 |
| Standard                              | n/a                                        | n/a                                     | n/a                                        | $0.10                                         | n/a                    | $0.02                     |
| Bulk                                  | n/a                                        | n/a                                     | n/a                                        | $0.025                                        | n/a                    | $0.0025                   |
| **S3 One Zone-Infrequent Access** **   | $0.01                                      | $0.001                                  | $0.01                                      | n/a                                           | n/a                    | n/a                       |


### Data Transfer Pricing

**Egress** - In networking terminology, egress refers to outbound data transfer from a network to another network or an individual server. For cloud providers, this means data that is transferred from one cloud provider's data centers to the public internet, another cloud provider, or to your own infrastructure.

Charges apply in the following scenarios:
 
- Data transferred **OUT From Amazon S3 To Internet**:
  - First 10 TB / Month: $0.09 per GB
  - Next 40 TB / Month: $0.085 per GB  
  - Next 100 TB / Month: $0.07 per GB
  - Greater than 150 TB / Month: $0.05 per GB
  
- Data transferred **from S3 to AWS services in a different region**: For example, accessing S3 data from an EC2 instance in another region.
  - From $0.01 per GB to \$0.08 per GB

Data transfers are free in these cases:

- Data transferred **out to the internet** for the first 100GB per month, aggregated across all AWS Services and Regions (except China and GovCloud)
- Data transferred **in from the internet**.
- Data transferred **from an Amazon S3 bucket to any AWS service(s) within the same AWS Region as the S3 bucket** (including to a different account in the same AWS Region).


## Cloudflare R2 Pricing (April 2025)

> Source: [Cloudflare R2 Pricing page](https://developers.cloudflare.com/r2/pricing/)

### Storage Pricing

**1. Normal Tier:**

| Storage Class                         | Tier / Description                                         | Price                    |
|--------------------------------------|------------------------------------------------------------|--------------------------|
| **Standard Storage**                 | General-purpose object storage                             | $0.015 per GB             |
| **Infrequent Access**                | For data accessed less frequently                          | $0.010 per GB             |

**2. Free Tier**

| Storage Class                         | Tier / Description                                         | Price                    |
|--------------------------------------|------------------------------------------------------------|--------------------------|
| **Free Tier**                        | If stored less then 10GB / month                           | Free                      |

### Operations Pricing

**1. Normal Tier:**

| Operation Type            | Standard Class              | Infrequent Access              | Notes                                                    |
|---------------------------|----------------------------|----------------------------|----------------------------------------------------------|
| **Class A Operations**       | $4.50 / million requests   | $9.0 / million requests   | Includes PUT, POST, DELETE (modifying data).           |
| **Class B Operations**       | $0.36 / million requests   | $0.9 / million requests   | Includes GET, LIST (reading data).                     |
| **Data Retrieval**           | None                       | $0.1 / million requests   | Processing data.                                       |

**Operation Types Legend:**
- **Class A Operations**: Write operations that modify data (PUT, POST, DELETE)
- **Class B Operations**: Read operations that retrieve data (GET, LIST)

**2. Free Tier**

| Operation Type            | Requirement             | Notes                                                    |
|---------------------------|----------------------------|----------------------------------------------------------|
| **Class A Operations**       | If less than 1 million requests per month   | Includes PUT, POST, DELETE (modifying data).  |
| **Class B Operations**       | If less than 10 million requests per month  | Includes GET, LIST (reading data).            |
| **Data Retrieval**           | None                       | Processing data.                                       |

Data transfers are **free** in these cases:

- Data transferred **out to the internet** is **always free** (no egress charges).
- Data transferred **within Cloudflare's network** (e.g., to Workers, CDN, Pages) is free.
- No charges for data **ingress** (uploading into R2).


## S3 vs R2 — Pricing Comparison (April 2025)

| Aspect                         | Amazon S3                                    | Cloudflare R2                                |
|--------------------------------|----------------------------------------------|---------------------------------------------|
| Storage Cost (Standard)        | ~$0.023 per GB/month (first 50 TB)           | $0.015 per GB/month                         |
| Storage Cost (Infrequent Access) | ~$0.0125 per GB/month (S3 Standard-IA)       | $0.010 per GB/month (IA optional in R2)     |
| Storage Cost (Deep Archive)    | ~$0.00099 per GB/month (S3 Deep Archive)     | Not a separate tier (only IA for cold data) |
| PUT / POST / DELETE Operations | ~$5.00 per million (PUT, POST)               | ~$4.50 per million (Class A operations)     |
| GET / LIST Operations          | ~$0.40 per million (GET, LIST)               | ~$0.36 per million (Class B operations)     |
| Egress to Internet             | $0.09/GB (first 10 TB/month)                 | Free                                         |
| Intra-region Transfer (S3 to EC2/Lambda/etc.) | Free                              | Free (within Cloudflare's network)          |
| Retrieval Cost (Cold Storage)  | Varies (e.g., $0.01/GB from S3 IA)           | $0.01/GB for retrieval from Infrequent Access |
| Free Tier                      | 5 GB storage + 20,000 GET + 2,000 PUT requests per month | 10 GB storage + 1M Class A + 10M Class B ops + unlimited egress |


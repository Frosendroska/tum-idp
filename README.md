# [IDP] Replacing AWS S3 with Cloudflare R2: Cost Analysis and Feasibility Study

This interdisciplinary project explores the feasibility and financial implications of replacing Amazon S3 with Cloudflare R2 as an object storage solution. Cloudflare R2 offers a competitive alternative with S3-compatible APIs, eliminating egress costs to the public internet. This project aims to assess whether migrating from AWS S3 to Cloudflare R2 can result in substantial cost savings while maintaining performance and reliability.

## Project Structure

### 1. [Project Kickoff & Literature Review](notes/1-project-kickoff.md)
> Research existing object storage solutions and cost structures.\
Define evaluation criteria for comparing AWS S3 and Cloudflare R2.\
Identify key performance indicators (KPIs) such as latency, egress costs, and API compatibility.

### 2. [Financial Analysis](notes/2-financial-analysis.md)
> Calculate total cost of ownership (TCO) based on real-world use cases for both S3 and R2.\
Analyze cost-saving potential and risk factors when integrating R2 with Amazon, Google, and Microsoft clouds.\
Evaluate pricing models and potential hidden costs of using Cloudflare R2.

### 3. [Implementation of Performance Tests & Monitoring](notes/3-performance-tests.md)
> Set up test environments for AWS S3, Cloudflare R2.\
Develop automated testing scripts to evaluate request throughput.\
Identify potential scalability challenges.

### 4. [Technical Benchmarking](notes/4-technical-benchmarking.md)
> Simulate real-world workloads to assess performance and stability, gradually increasing a scale.\
Measure latency, request performance, and data retrieval speed across multiple cloud environments.

### 5. [Documentation & Presentation Preparation](notes/5-documentation.md)
> Compile results into a structured report with technical findings and financial assessments.\
Prepare a final presentation summarizing key insights and practical recommendations.

## Timeline
- March 2025: Project Kickoff & Literature Review
- April 2025: Financial Analysis
- May 2025: Implementation of Performance Tests & Monitoring
- June 2025: Technical Benchmarking
- July 2025: Documentation & Presentation Preparation

## Important links

- Project description: [[GoogleDocs](https://docs.google.com/document/d/1j7r3w-ZQyOZsmdqYzyyUJghaHzooTu6h3ejlI9FZICs/edit?tab=t.0#heading=h.uzx2xxidnmp0)]
- Project notes: [[File in this repo](/notes/main-notes.md)]
- Final document: [[Overleaf](https://www.overleaf.com/read/hwsttkkzjnyb#c92dd1)]

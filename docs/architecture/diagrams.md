<file_path>
noaa_storefront/docs/architecture/diagrams.md
</file_path>
# NOAA Federated Data Lake Architecture Diagrams

This document contains text-based architecture diagrams and visual representations of the NOAA Federated Data Lake system components, data flows, and deployment architecture.

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          NOAA Federated Data Lake                        │
│                          =======================                         │
├─────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │
│ │ Atmospheric │ │  Oceanic    │ │   Climate   │ │   Buoy      │        │
│ │    Pond     │ │    Pond     │ │    Pond     │ │    Pond     │        │
│ │ (Weather)   │ │ (Marine)    │ │ (Climate)   │ │ (Buoy)      │        │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘        │
│                                                                         │
│ ┌─────────────┐ ┌─────────────┐                                         │
│ │  Spatial    │ │ Terrestrial │                                         │
│ │   Pond      │ │    Pond     │                                         │
│ │ (Sat/Radar) │ │ (Rivers)    │                                         │
│ └─────────────┘ └─────────────┘                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                    AI Query Orchestrator                                │
├─────────────────────────────────────────────────────────────────────────┤
│ Federated Athena Queries • Intelligent Data Routing • Response Synth. │
└─────────────────────────────────────────────────────────────────────────┘
```

## 2. Medallion Architecture

```
Raw Data (Bronze) → Processed Data (Silver) → Analytics Ready (Gold)
       ↓                       ↓                         ↓
   ┌─────────────┐       ┌─────────────┐         ┌─────────────┐
   │   JSON      │       │   Parquet   │         │   Parquet   │
   │   (API      │       │   (Cleaned  │         │   (Aggreg.  │
   │   Response) │       │   Data)     │         │   Data)     │
   └─────────────┘       └─────────────┘         └─────────────┘
         90 days              365 days               730 days
```

## 3. Data Ingestion Flow

```
NOAA APIs (25+) → Lambda Ingestion Functions → S3 Bronze Layer → Glue ETL → S3 Silver Layer → Athena → S3 Gold Layer
                      ↑                           ↑                    ↑
              EventBridge Schedules      Data Validation      Aggregation & Indexing
              (15min - 1hr intervals)    (Schema, Nulls)       (Cross-pond joins)
```

## 4. AI Query Processing

```
User Query → API Gateway → Enhanced Handler Lambda → Bedrock (Claude 3.5) → Pond Selection
                                                                                   ↓
                         Parallel Pond Queries → Athena Federated Queries → Response Synthesis
                                                                                   ↓
                                                             Formatted Response
```

## 5. AWS Service Integration

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │    │    Lambda       │    │    Bedrock      │
│   (Endpoints)   │◄──►│ (Handlers)      │◄──►│ (AI Models)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ EventBridge     │    │      S3         │    │    Athena       │
│ (Scheduling)    │◄──►│ (Data Lake)     │◄──►│ (Federated      │
└─────────────────┘    └─────────────────┘    │    Queries)     │
         │                       │           └─────────────────┘
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│ CloudWatch      │    │   Glue/ETL      │
│ (Monitoring)    │    │ (Transform)     │
└─────────────────┘    └─────────────────┘
```

## 6. Security Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Defense in Depth                             │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │           Public Internet                                       │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                           ↓                                          │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │           API Gateway (WAF, Throttling, Auth)                   │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                           ↓                                          │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │           VPC Endpoints (Private Networking)                    │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                           ↓                                          │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │           IAM Roles (Least Privilege)                           │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                           ↓                                          │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │           S3 (Encryption at Rest)                               │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│                           ↓                                          │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │           Data Encryption in Transit                            │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## 7. Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AWS Regions                                  │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐   │
│ │   us-east-1     │    │   us-west-2     │    │  us-gov-east-1  │   │
│ │  (Primary)      │    │   (DR)          │    │  (GovCloud)     │   │
│ └─────────────────┘    └─────────────────┘    └─────────────────┘   │
│         │                       │                       │           │
│         └───────────────────────┼───────────────────────┘           │
│                                 │                                   │
│                    ┌─────────────────┐                              │
│                    │ CloudFormation  │                              │
│                    │   Templates     │                              │
│                    └─────────────────┘                              │
│                                 │                                   │
│         ┌───────────┬───────────┼───────────┬───────────┐          │
│         │           │           │           │           │          │
│     ┌───▼───┐   ┌───▼───┐   ┌───▼───┐   ┌───▼───┐   │
│     │Lambda │   │  S3   │   │Athena │   │Bedrock│   │
│     └───────┘   └───────┘   └───────┘   └───────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## 8. Data Flow Example

```
User: "What's the weather and wave conditions for Boston Harbor?"

1. Query Reception → API Gateway
2. AI Processing → Enhanced Handler Lambda
3. Pond Selection → Atmospheric + Oceanic Ponds
4. Parallel Queries → Lambda functions query Athena
5. Data Synthesis → AI combines weather + marine data
6. Response → Formatted maritime analysis
```

## 9. Scalability Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Horizontal Scaling                           │
├─────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐   │
│ │  Lambda (1)     │    │   Lambda (N)    │    │   Auto-scaling   │   │
│ │  Concurrent     │◄──►│   Requests      │◄──►│   Based on Load  │   │
│ └─────────────────┘    └─────────────────┘    └─────────────────┘   │
│         ↑                       ↑                       ↑           │
│ ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐   │
│ │ EventBridge     │    │      S3         │    │     Athena       │   │
│ │ Schedules       │    │ (Partitioned)   │    │ (Federated)     │   │
│ └─────────────────┘    └─────────────────┘    └─────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

These diagrams provide a visual representation of the system's architecture. For actual deployment, refer to the CloudFormation templates and deployment scripts in the project.
```
**continue with the implementation.**

Continue with other changes. Now, modify maritime-chatbot.py to accept --region and --function-name.
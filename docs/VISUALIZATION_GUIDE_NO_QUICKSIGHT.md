# NOAA Federated Data Lake - Visualization Guide (Without QuickSight)

## 📊 Overview

This guide provides **multiple alternatives to QuickSight** for visualizing your NOAA Federated Data Lake, including:
- Data ingestion monitoring
- Medallion architecture flow (Bronze → Silver → Gold)
- AI query processing visualization
- System health and performance metrics

---

## 🎯 Visualization Options

### Option 1: CloudWatch Dashboards (Recommended - Free)
### Option 2: Standalone HTML Dashboard (Zero Setup)
### Option 3: Grafana + CloudWatch (Advanced)
### Option 4: Athena + Jupyter Notebooks (Analytics)
### Option 5: CLI Monitoring Tools (Operational)

---

## 🔥 Option 1: CloudWatch Dashboards (Recommended)

**Cost:** FREE (included with AWS)  
**Setup Time:** 5 minutes  
**Best For:** Real-time monitoring, operational dashboards

### Deploy CloudWatch Dashboards

```bash
cd monitoring
chmod +x create_cloudwatch_dashboards.sh
./create_cloudwatch_dashboards.sh
```

This creates **5 comprehensive dashboards**:

#### Dashboard 1: Data Ingestion Flow
**URL:** https://console.aws.amazon.com/cloudwatch/dashboards/NOAA-Data-Ingestion-Flow-dev

**Shows:**
- Lambda invocations by pond (real-time)
- Success rate % for each data source
- Records written to Bronze layer
- Average ingestion duration
- Recent ingestion events (live logs)

#### Dashboard 2: Medallion Architecture Flow
**URL:** https://console.aws.amazon.com/cloudwatch/dashboards/NOAA-Medallion-Architecture-dev

**Shows:**
- Bronze layer → Raw data ingestion metrics
- Silver layer → Processed data with quality scores
- Gold layer → Analytics-ready records
- Glue job executions (ETL pipeline)
- Conversion rate: Bronze → Gold (%)
- Step Functions pipeline execution times

#### Dashboard 3: AI Query Processing
**URL:** https://console.aws.amazon.com/cloudwatch/dashboards/NOAA-AI-Query-Processing-dev

**Shows:**
- AI query volume and response times
- Bedrock API calls and latency
- Number of ponds queried per request
- Query interpretation success rate
- Athena query execution stats
- Result set sizes and cache hit rates

#### Dashboard 4: System Health Overview
**URL:** https://console.aws.amazon.com/cloudwatch/dashboards/NOAA-System-Health-Overview-dev

**Shows:**
- Overall system health score (0-100)
- Total records processed (24h)
- Active Lambda functions
- Query success rate
- Data quality scores (completeness, timeliness, accuracy)
- Cost metrics and alarms

#### Dashboard 5: Data Flow Visualization
**URL:** https://console.aws.amazon.com/cloudwatch/dashboards/NOAA-Data-Flow-Visualization-dev

**Shows:**
- Step-by-step flow visualization
- API Calls → Lambda → Bronze → ETL → Gold → Athena → Results
- Each step shows volume and performance
- End-to-end latency tracking

### Access Dashboards

```bash
# Open in browser
open "https://console.aws.amazon.com/cloudwatch/dashboards/NOAA-Data-Ingestion-Flow-dev?region=us-east-1"

# Or use AWS CLI to view metrics
aws cloudwatch get-dashboard \
  --dashboard-name NOAA-Data-Ingestion-Flow-dev \
  --profile noaa-target \
  --region us-east-1
```

### Custom Metrics for Enhanced Visualization

Add custom metrics to your Lambda functions:

```python
# In your Lambda ingestion functions
import boto3
cloudwatch = boto3.client('cloudwatch')

# Track ingestion
cloudwatch.put_metric_data(
    Namespace='NOAA/DataLake',
    MetricData=[
        {
            'MetricName': 'BronzeRecords',
            'Value': record_count,
            'Unit': 'Count',
            'Dimensions': [
                {'Name': 'Pond', 'Value': 'atmospheric'}
            ]
        }
    ]
)
```

---

## 🌐 Option 2: Standalone HTML Dashboard

**Cost:** FREE  
**Setup Time:** 1 minute (just open file)  
**Best For:** Local monitoring, demos, presentations

### Setup

```bash
cd monitoring

# Open in browser
open dashboard.html

# Or use Python web server
python3 -m http.server 8080
# Then open: http://localhost:8080/dashboard.html
```

### Features

✅ **Real-time Data Flow Visualization**
- Interactive flow diagram: API → Bronze → Silver → Gold → Query
- Live metrics and counters
- Color-coded status indicators

✅ **AI Query Interface**
- Natural language query input
- Shows how AI interprets queries
- Displays which ponds are queried
- Shows query results

✅ **Performance Charts**
- Ingestion by pond (bar chart)
- Conversion rate over time (line chart)
- System performance metrics

✅ **Live System Logs**
- Recent ingestion events
- Query processing logs
- Error tracking

### Connect to AWS (Optional)

Configure AWS credentials in the dashboard:

1. Click "⚙️ Configure AWS Credentials"
2. Enter Access Key and Secret Key
3. Dashboard will fetch live data from CloudWatch

**Note:** For security, use IAM roles instead of hardcoded credentials in production.

### Demo Mode

The dashboard works in **demo mode** without AWS credentials:
- Shows simulated data flow
- Demonstrates all visualizations
- Perfect for presentations and training

---

## 📊 Option 3: Grafana + CloudWatch

**Cost:** FREE (self-hosted) or $9/month (Grafana Cloud)  
**Setup Time:** 30 minutes  
**Best For:** Advanced dashboards, alerting, multi-source data

### Install Grafana

```bash
# Docker (easiest)
docker run -d -p 3000:3000 --name=grafana grafana/grafana-enterprise

# Or use Homebrew (Mac)
brew install grafana
brew services start grafana

# Access at: http://localhost:3000
# Default login: admin/admin
```

### Configure CloudWatch Data Source

1. Open Grafana: http://localhost:3000
2. Go to **Configuration → Data Sources**
3. Click **Add data source**
4. Select **CloudWatch**
5. Configure:
   - **Authentication**: AWS SDK Default
   - **Default Region**: us-east-1
   - **Assume Role ARN**: (leave blank if using local credentials)
6. Click **Save & Test**

### Import Pre-built Dashboards

```bash
# Download Grafana dashboard JSON
aws s3 cp s3://noaa-federated-lake-899626030376-dev/grafana-dashboards/ . --recursive --profile noaa-target

# Or use our templates
cd monitoring/grafana-templates/
```

### Create Custom Dashboard

**Dashboard 1: Data Lake Overview**

```json
{
  "dashboard": {
    "title": "NOAA Data Lake Overview",
    "panels": [
      {
        "title": "Lambda Invocations",
        "targets": [
          {
            "namespace": "AWS/Lambda",
            "metricName": "Invocations",
            "dimensions": {
              "FunctionName": "noaa-ingest-atmospheric-dev"
            },
            "statistic": "Sum",
            "period": "300"
          }
        ]
      }
    ]
  }
}
```

### Grafana Features

✅ **Advanced Visualizations**
- Time series graphs
- Heat maps
- Gauge panels
- Stat panels
- Tables with sorting/filtering

✅ **Alerting**
- Alert on any metric threshold
- Send to Slack, PagerDuty, email
- Define alert rules and notification channels

✅ **Variables**
- Dynamic dashboards with dropdowns
- Select pond, time range, environment
- Reusable dashboard templates

---

## 📓 Option 4: Jupyter Notebooks + Athena

**Cost:** FREE  
**Setup Time:** 15 minutes  
**Best For:** Data exploration, analysis, reporting

### Setup Jupyter

```bash
# Install dependencies
pip install jupyter pandas boto3 pyathena matplotlib seaborn

# Start Jupyter
jupyter notebook
```

### Create Visualization Notebook

```python
# notebook: NOAA_Data_Visualization.ipynb

import pandas as pd
from pyathena import connect
import matplotlib.pyplot as plt
import seaborn as sns

# Connect to Athena
conn = connect(
    s3_staging_dir='s3://noaa-athena-results-899626030376-dev/',
    region_name='us-east-1'
)

# Query Gold layer data
df = pd.read_sql("""
    SELECT 
        pond_name,
        COUNT(*) as record_count,
        AVG(quality_score) as avg_quality
    FROM noaa_gold_dev.atmospheric
    WHERE year = 2024 AND month = 12
    GROUP BY pond_name
""", conn)

# Visualize
plt.figure(figsize=(12, 6))
sns.barplot(data=df, x='pond_name', y='record_count')
plt.title('Records by Pond')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
```

### Pre-built Notebook Examples

#### Notebook 1: Ingestion Analysis
```python
# Analyze ingestion patterns
df_ingestion = pd.read_sql("""
    SELECT 
        DATE_TRUNC('hour', observation_time) as hour,
        COUNT(*) as records
    FROM noaa_gold_dev.atmospheric
    WHERE observation_time >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR
    GROUP BY DATE_TRUNC('hour', observation_time)
    ORDER BY hour
""", conn)

# Plot time series
df_ingestion.plot(x='hour', y='records', kind='line', figsize=(14, 6))
plt.title('Ingestion Rate Over Time')
plt.ylabel('Records per Hour')
plt.show()
```

#### Notebook 2: Medallion Flow Analysis
```python
# Analyze Bronze → Gold conversion
query = """
WITH bronze_counts AS (
    SELECT DATE(ingestion_timestamp) as date, COUNT(*) as bronze
    FROM noaa_datalake_dev.bronze_atmospheric
    WHERE ingestion_timestamp >= CURRENT_DATE - INTERVAL '7' DAY
    GROUP BY DATE(ingestion_timestamp)
),
gold_counts AS (
    SELECT DATE(processing_timestamp) as date, COUNT(*) as gold
    FROM noaa_gold_dev.atmospheric
    WHERE processing_timestamp >= CURRENT_DATE - INTERVAL '7' DAY
    GROUP BY DATE(processing_timestamp)
)
SELECT 
    b.date,
    b.bronze,
    g.gold,
    ROUND(100.0 * g.gold / b.bronze, 2) as conversion_rate
FROM bronze_counts b
JOIN gold_counts g ON b.date = g.date
ORDER BY b.date
"""

df_conversion = pd.read_sql(query, conn)

# Visualize conversion funnel
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

# Volume over time
df_conversion[['bronze', 'gold']].plot(kind='bar', ax=ax1)
ax1.set_title('Bronze vs Gold Volume')
ax1.set_ylabel('Records')

# Conversion rate
df_conversion['conversion_rate'].plot(kind='line', ax=ax2, marker='o')
ax2.set_title('Conversion Rate Over Time')
ax2.set_ylabel('Conversion Rate (%)')
ax2.axhline(y=95, color='r', linestyle='--', label='Target (95%)')
ax2.legend()

plt.tight_layout()
plt.show()
```

#### Notebook 3: AI Query Analysis
```python
# Analyze AI query patterns from CloudWatch Logs
import boto3

logs = boto3.client('logs', region_name='us-east-1')

# Query logs
response = logs.filter_log_events(
    logGroupName='/aws/lambda/noaa-ai-query-dev',
    filterPattern='User query',
    startTime=int((datetime.now() - timedelta(days=7)).timestamp() * 1000)
)

# Extract query patterns
queries = []
for event in response['events']:
    if 'User query:' in event['message']:
        query = event['message'].split('User query:')[1].strip()
        queries.append(query)

# Analyze common patterns
from collections import Counter
query_words = ' '.join(queries).lower().split()
common_terms = Counter(query_words).most_common(20)

# Visualize
words, counts = zip(*common_terms)
plt.figure(figsize=(12, 6))
plt.bar(words, counts)
plt.xticks(rotation=45, ha='right')
plt.title('Most Common Query Terms')
plt.tight_layout()
plt.show()
```

---

## 🖥️ Option 5: CLI Monitoring Tools

**Cost:** FREE  
**Setup Time:** 5 minutes  
**Best For:** Operations, troubleshooting, automation

### Install CLI Tools

```bash
cd monitoring

# Make scripts executable
chmod +x *.sh
```

### Monitor Data Flow

```bash
#!/bin/bash
# monitor_data_flow.sh

echo "=== NOAA Data Lake - Real-time Flow Monitor ==="
echo ""

while true; do
    clear
    echo "📊 Data Flow Status - $(date)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # 1. Ingestion (Lambda invocations)
    echo "1️⃣  INGESTION (Last 5 min)"
    aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Invocations \
        --dimensions Name=FunctionName,Value=noaa-ingest-atmospheric-dev \
        --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
        --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
        --period 300 \
        --statistics Sum \
        --profile noaa-target \
        --query 'Datapoints[0].Sum' \
        --output text | xargs -I {} echo "   Atmospheric: {} invocations"
    
    # 2. Bronze Layer (S3 objects)
    echo ""
    echo "2️⃣  BRONZE LAYER"
    aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/atmospheric/ \
        --recursive --profile noaa-target | wc -l | xargs -I {} echo "   Files: {}"
    
    # 3. ETL Processing (Glue jobs)
    echo ""
    echo "3️⃣  ETL PROCESSING"
    aws glue get-job-runs \
        --job-name noaa-bronze-to-gold-atmospheric-dev \
        --max-results 1 \
        --profile noaa-target \
        --query 'JobRuns[0].JobRunState' \
        --output text | xargs -I {} echo "   Status: {}"
    
    # 4. Gold Layer
    echo ""
    echo "4️⃣  GOLD LAYER"
    aws athena start-query-execution \
        --query-string "SELECT COUNT(*) as count FROM noaa_gold_dev.atmospheric WHERE year=2024 AND month=12" \
        --result-configuration "OutputLocation=s3://noaa-athena-results-899626030376-dev/" \
        --profile noaa-target \
        --query 'QueryExecutionId' \
        --output text > /tmp/query_id.txt
    
    sleep 2
    aws athena get-query-results \
        --query-execution-id $(cat /tmp/query_id.txt) \
        --profile noaa-target \
        --query 'ResultSet.Rows[1].Data[0].VarCharValue' \
        --output text | xargs -I {} echo "   Records: {}"
    
    # 5. AI Queries
    echo ""
    echo "5️⃣  AI QUERIES (Last hour)"
    aws cloudwatch get-metric-statistics \
        --namespace AWS/Lambda \
        --metric-name Invocations \
        --dimensions Name=FunctionName,Value=noaa-ai-query-dev \
        --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
        --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
        --period 3600 \
        --statistics Sum \
        --profile noaa-target \
        --query 'Datapoints[0].Sum' \
        --output text | xargs -I {} echo "   Queries: {}"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Refreshing in 30 seconds... (Ctrl+C to stop)"
    sleep 30
done
```

### Run Monitor

```bash
./monitor_data_flow.sh
```

### Additional CLI Tools

#### Check System Health
```bash
#!/bin/bash
# check_health.sh

echo "🏥 System Health Check"
echo ""

# Lambda errors
echo "Lambda Errors (last hour):"
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Errors \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 3600 \
    --statistics Sum \
    --profile noaa-target

# Glue job status
echo ""
echo "Recent Glue Job Runs:"
aws glue get-job-runs \
    --max-results 5 \
    --profile noaa-target \
    --query 'JobRuns[*].[JobName,JobRunState,StartedOn]' \
    --output table

# S3 bucket sizes
echo ""
echo "Storage by Layer:"
aws s3 ls s3://noaa-federated-lake-899626030376-dev/ \
    --summarize --recursive --human-readable --profile noaa-target | grep "Total Size"
```

#### View Recent Logs
```bash
#!/bin/bash
# view_logs.sh

FUNCTION_NAME=${1:-noaa-ingest-atmospheric-dev}

echo "📝 Recent logs from $FUNCTION_NAME"
echo ""

aws logs tail /aws/lambda/$FUNCTION_NAME \
    --follow \
    --format short \
    --since 10m \
    --profile noaa-target
```

#### Query Data
```bash
#!/bin/bash
# query_data.sh

QUERY=${1:-"SELECT * FROM noaa_gold_dev.atmospheric LIMIT 10"}

echo "Running query: $QUERY"
echo ""

# Start query
QUERY_ID=$(aws athena start-query-execution \
    --query-string "$QUERY" \
    --result-configuration "OutputLocation=s3://noaa-athena-results-899626030376-dev/" \
    --profile noaa-target \
    --query 'QueryExecutionId' \
    --output text)

echo "Query ID: $QUERY_ID"
echo "Waiting for results..."

# Wait for completion
while true; do
    STATE=$(aws athena get-query-execution \
        --query-execution-id $QUERY_ID \
        --profile noaa-target \
        --query 'QueryExecution.Status.State' \
        --output text)
    
    if [ "$STATE" = "SUCCEEDED" ]; then
        break
    elif [ "$STATE" = "FAILED" ] || [ "$STATE" = "CANCELLED" ]; then
        echo "Query failed!"
        exit 1
    fi
    
    sleep 1
done

# Get results
aws athena get-query-results \
    --query-execution-id $QUERY_ID \
    --profile noaa-target \
    --output table
```

---

## 📊 Comparison Matrix

| Feature | CloudWatch | HTML Dashboard | Grafana | Jupyter | CLI Tools |
|---------|------------|----------------|---------|---------|-----------|
| **Cost** | FREE | FREE | FREE/$9 | FREE | FREE |
| **Setup Time** | 5 min | 1 min | 30 min | 15 min | 5 min |
| **Real-time** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |
| **Customization** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **AWS Integration** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Alerting** | ✅ Built-in | ❌ No | ✅ Advanced | ❌ No | ⚠️ Manual |
| **Mobile Access** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No | ❌ No |
| **Best For** | Operations | Demos | Production | Analysis | Automation |

---

## 🎯 Recommended Setup

### For Most Users (Complete Stack)

1. **CloudWatch Dashboards** - Primary operational monitoring
2. **HTML Dashboard** - Quick local access and demos
3. **CLI Tools** - Troubleshooting and automation

### For Advanced Users

Add:
4. **Grafana** - Advanced visualizations and alerting
5. **Jupyter Notebooks** - Deep data analysis

### Quick Start

```bash
# 1. Deploy CloudWatch Dashboards
cd monitoring
./create_cloudwatch_dashboards.sh

# 2. Open HTML Dashboard
open dashboard.html

# 3. Start monitoring
./monitor_data_flow.sh
```

---

## 📈 Visualizing Key Flows

### 1. Data Ingestion Flow

**CloudWatch Dashboard:** NOAA-Data-Ingestion-Flow-dev

**Shows:**
```
NOAA APIs → Lambda Functions → S3 Bronze Layer
     ↓             ↓                    ↓
API Calls    Invocations          Files Written
  (count)      (count)             (count/size)
```

**Metrics to Watch:**
- Lambda invocations per pond
- Success rate (should be >99%)
- Average duration (should be <5 seconds)
- Error count (should be near 0)

### 2. Medallion Architecture Flow

**CloudWatch Dashboard:** NOAA-Medallion-Architecture-dev

**Shows:**
```
Bronze (Raw) → Silver (Processed) → Gold (Analytics)
     ↓                ↓                     ↓
  77K files       Quality Check          75K records
  (JSON)          (validation)           (Parquet)
                      ↓
              99.5% conversion rate
```

**Metrics to Watch:**
- Conversion rate Bronze → Gold (target: >95%)
- Data quality score (target: >90%)
- Processing time (target: <30 min)
- Glue job success rate

### 3. AI Query Processing

**CloudWatch Dashboard:** NOAA-AI-Query-Processing-dev

**Shows:**
```
User Question → AI Interpretation → Pond Selection → Athena Query → Results
      ↓               ↓                   ↓               ↓            ↓
  "temperature"  Extract intent     2-4 ponds        SQL query    Formatted
   last week      + entities        (relevance)      execution     response
```

**Metrics to Watch:**
- Query volume (queries per day)
- Response time (target: <5 seconds)
- Interpretation success (target: >95%)
- Ponds queried per request
- Cache hit rate

### 4. System Health Flow

**CloudWatch Dashboard:** NOAA-System-Health-Overview-dev

**Shows:**
```
┌─────────────────────────────────────────┐
│  Overall Health Score: 98/100           │
├─────────────────────────────────────────┤
│  ✅ Ingestion: Healthy                  │
│  ✅ Processing: Healthy                 │
│  ✅ Storage: 55.7 GB (45% capacity)     │
│  ✅ Queries: 247 today (99.5% success)  │
│  ⚠️  Warnings: 2 (low priority)         │
└─────────────────────────────────────────┘
```

---

## 🔍 Querying and Exploring Data

### Using Athena Console

1. **Open Athena Console**
   ```
   https://console.aws.amazon.com/athena/home?region=us-east-1
   ```

2. **Select Database**
   ```sql
   -- View available databases
   SHOW DATABASES;
   
   -- Use Gold layer
   USE noaa_gold_dev;
   
   -- List tables
   SHOW TABLES;
   ```

3. **Explore Data**
   ```sql
   -- Sample atmospheric data
   SELECT * FROM atmospheric 
   WHERE year = 2024 AND month = 12
   LIMIT 100;
   
   -- Count records by pond
   SELECT 
       'atmospheric' as pond,
       COUNT(*) as record_count
   FROM atmospheric
   WHERE year = 2024
   UNION ALL
   SELECT 
       'oceanic' as pond,
       COUNT(*) as record_count
   FROM oceanic
   WHERE year = 2024;
   
   -- Track conversion rates
   SELECT 
       DATE(processing_timestamp) as date,
       COUNT(*) as records_processed,
       AVG(quality_score) as avg_quality
   FROM atmospheric
   WHERE year = 2024 AND month = 12
   GROUP BY DATE(processing_timestamp)
   ORDER BY date DESC;
   ```

4. **Export Results**
   - Click "Download results" button
   - Or access from S3: `s3://noaa-athena-results-899626030376-dev/`

---

## 🚨 Setting Up Alerts

### CloudWatch Alarms

```bash
# Create alarm for high error rate
aws cloudwatch put-metric-alarm \
    --alarm-name noaa-ingestion-errors-high \
    --alarm-description "Alert when ingestion error rate exceeds 5%" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 300 \
    --evaluation-periods 2 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=FunctionName,Value=noaa-ingest-atmospheric-dev \
    --profile noaa-target

# Create alarm for low data volume
aws cloudwatch put-metric-alarm \
    --alarm-name noaa-ingestion-volume-low \
    --alarm-description "Alert when no data ingested for 30 minutes" \
    --metric-name Invocations \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 1800 \
    --evaluation-periods 1 \
    --threshold 1 \
    --comparison-operator LessThanThreshold \
    --dimensions Name=FunctionName,Value=noaa-ingest-atmospheric-dev \
    --profile noaa-target
```

### SNS Notifications

```bash
# Create SNS topic
aws sns create-topic \
    --name noaa-alerts \
    --profile noaa-target

# Subscribe email
aws sns subscribe \
    --topic-arn arn:aws:sns:us-east-1:899626030376:noaa-alerts \
    --protocol email \
    --notification-endpoint your-email@domain.com \
    --profile noaa-target

# Link alarm to SNS
aws cloudwatch put-metric-alarm \
    --alarm-name noaa-critical-alert \
    --alarm-actions arn:aws:sns:us-east-1:899626030376:noaa-alerts \
    ... # other alarm parameters
```

---

## 📚 Additional Resources

### AWS Console Quick Links

| Resource | URL |
|----------|-----|
| CloudWatch Dashboards | https://console.aws.amazon.com/cloudwatch/dashboards |
| CloudWatch Logs | https://console.aws.amazon.com/cloudwatch/logs |
| Athena Query Editor | https://console.aws.amazon.com/athena |
| Glue Jobs | https://console.aws.amazon.com/glue/home#etl:tab=jobs |
| S3 Buckets | https://s3.console.aws.amazon.com/s3/buckets/noaa-federated-lake-899626030376-dev |
| Lambda Functions | https://console.aws.amazon.com/lambda/home#/functions |
| Step Functions | https://console.aws.amazon.com/states/home#/statemachines |

### Useful Athena Queries

```sql
-- System health check
SELECT 
    COUNT(*) as total_records,
    COUNT(DISTINCT station_id) as unique_stations,
    MIN(observation_time) as oldest_record,
    MAX(observation_time) as newest_record,
    AVG(quality_score) as avg_quality
FROM noaa_gold_dev.atmospheric
WHERE year = 2024 AND month = 12;

-- Find data gaps
SELECT 
    DATE(observation_time) as date,
    COUNT(*) as record_count
FROM noaa_gold_dev.atmospheric
WHERE year = 2024 AND month = 12
GROUP BY DATE(observation_time)
HAVING COUNT(*) < 100
ORDER BY date;

-- Top stations by volume
SELECT 
    station_id,
    COUNT(*) as observations,
    AVG(temperature) as avg_temp
FROM noaa_gold_dev.atmospheric
WHERE year = 2024 AND month = 12
GROUP BY station_id
ORDER BY observations DESC
LIMIT 20;
```

---

## 🎓 Training & Documentation

### Video Tutorials (Create These)

1. **Introduction to CloudWatch Dashboards** (10 min)
2. **Using the HTML Dashboard** (5 min)
3. **Querying Data with Athena** (15 min)
4. **Setting Up Grafana** (20 min)
5. **CLI Monitoring Tools** (10 min)

### Quick Reference Cards

Print these for your team:
- CloudWatch Dashboard URLs
- Common Athena queries
- CLI command cheatsheet
- Troubleshooting flowchart

---

## ✅ Next Steps

1. **Deploy CloudWatch Dashboards**
   ```bash
   cd monitoring
   ./create_cloudwatch_dashboards.sh
   ```

2. **Open HTML Dashboard**
   ```bash
   open dashboard.html
   ```

3. **Bookmark Console URLs**
   - Save CloudWatch dashboard links
   - Save Athena console link

4. **Set Up Alerts**
   - Configure SNS topic
   - Create critical alarms

5. **Train Your Team**
   - Share dashboard URLs
   - Conduct walkthrough session

---

**You now
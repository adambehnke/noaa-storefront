# NOAA Federated Data Lake - Monitoring Dashboards

## 🎯 Overview

This directory contains two visualization solutions for monitoring your NOAA Federated Data Lake **without QuickSight**:

1. **CloudWatch Dashboards** - Real-time AWS monitoring (FREE)
2. **HTML Dashboards** - Standalone web dashboards (FREE)

---

## 🚀 Quick Start

### Deploy Everything (Recommended)

```bash
cd monitoring
chmod +x deploy_dashboards.sh
./deploy_dashboards.sh all
```

**That's it!** You'll have:
- ✅ 3 CloudWatch dashboards in AWS Console
- ✅ 2 HTML dashboards ready to open locally
- ✅ Quick launch scripts

---

## 📊 Option 1: CloudWatch Dashboards

### Deploy

```bash
./deploy_dashboards.sh cloudwatch
```

### Access

Open your browser to:
- **Data Ingestion Flow**: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=NOAA-Data-Ingestion-Flow-dev
- **System Health**: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=NOAA-System-Health-dev
- **AI Query Processing**: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=NOAA-AI-Query-Processing-dev

### What You'll See

#### Dashboard 1: Data Ingestion Flow
- Lambda invocations by pond (Atmospheric, Oceanic, Buoy, etc.)
- Success rates and error counts
- Average ingestion duration
- Concurrent executions

**Use this to:**
- Monitor real-time data ingestion
- Spot ingestion failures
- Track performance trends

#### Dashboard 2: System Health
- Total invocations (24h)
- Error counts and rates
- Glue job status
- Step Functions executions
- Overall system health

**Use this to:**
- Quick health check
- Identify system-wide issues
- Monitor error rates

#### Dashboard 3: AI Query Processing
- AI query volume and response times
- Query success rates
- Athena query performance
- Data scanned metrics

**Use this to:**
- Monitor AI query usage
- Track query performance
- Optimize query costs

---

## 🌐 Option 2: HTML Dashboards

### Deploy

```bash
./deploy_dashboards.sh html
```

### Access

```bash
# Quick launch (opens both dashboards)
./open_dashboards.sh

# Or open manually
open dashboard_configured.html        # Simple dashboard with links
open dashboard_interactive.html       # Full interactive dashboard
```

### Two Dashboard Types

#### A. Simple Dashboard (`dashboard_configured.html`)
- Clean, static dashboard with links to CloudWatch
- System architecture overview
- Quick commands for data queries
- Direct links to AWS Console
- **Best for:** Quick reference, sharing with team

#### B. Interactive Dashboard (`dashboard_interactive.html`)
- Live data flow visualization
- Real-time metrics and charts
- AI query interface (demo mode)
- Performance metrics
- System logs display
- **Best for:** Live monitoring, presentations, demos

---

## 📈 What Each Dashboard Shows

### Data Ingestion Monitoring

**CloudWatch:**
```
Lambda Invocations → Error Rates → Duration → Concurrent Executions
```

**HTML Dashboard:**
```
API Calls → Bronze Records → Silver Processing → Gold Layer → Queries
```

### Medallion Architecture Flow

```
🥉 BRONZE (Raw)
   ↓
   77,542 files
   ↓
🥈 SILVER (Processed)
   ↓
   Quality Score: 98%
   ↓
🥇 GOLD (Analytics)
   ↓
   75,234 records
   ↓
🔍 QUERIES (AI)
   ↓
   247 queries today
```

### AI Query Processing

```
User Question
   ↓
Bedrock AI (Claude)
   ↓
Intent Extraction
   ↓
Pond Selection (2-4 ponds)
   ↓
Parallel Athena Queries
   ↓
Result Aggregation
   ↓
Natural Language Response
```

---

## 🔧 Configuration

### AWS Credentials

CloudWatch dashboards use your AWS CLI profile:

```bash
# Verify credentials
aws sts get-caller-identity --profile noaa-target

# Should show Account: 899626030376
```

### Environment Variables

All settings are in `../config/environment.sh`:

```bash
AWS_ACCOUNT_ID=899626030376
AWS_REGION=us-east-1
ENVIRONMENT=dev
```

---

## 🎨 Customization

### Add Custom Metrics

Edit `deploy_dashboards.sh` and add your metrics:

```bash
# Example: Add custom metric to dashboard
{
  "type": "metric",
  "properties": {
    "title": "My Custom Metric",
    "metrics": [
      ["NOAA/Custom", "MyMetric", {"stat": "Sum"}]
    ]
  }
}
```

### Modify HTML Dashboard

Edit `dashboard_interactive.html`:

```javascript
// Update refresh interval (default: 60 seconds)
setInterval(function() {
    refreshData();
}, 60000); // Change to 30000 for 30 seconds
```

---

## 📊 Using the Dashboards

### Monitor Daily Operations

**Morning Check:**
1. Open CloudWatch "System Health" dashboard
2. Check error count (should be near 0)
3. Verify invocations (should be ~900/day)
4. Review any alarms

**Ongoing Monitoring:**
1. Keep "Data Ingestion Flow" dashboard open
2. Watch for red spikes (errors)
3. Monitor duration trends

### Troubleshoot Issues

**High Error Rate:**
1. Open "Data Ingestion Flow" dashboard
2. Identify which pond is failing
3. Click through to Lambda function
4. Check CloudWatch Logs

**Slow Queries:**
1. Open "AI Query Processing" dashboard
2. Check query response times
3. Review Athena data scanned
4. Optimize queries if needed

### Present to Stakeholders

1. Open `dashboard_configured.html`
2. Show architecture overview
3. Click through to CloudWatch for live data
4. Demonstrate system health

---

## 🔍 Quick Commands

### View Real-Time Logs

```bash
# Atmospheric ingestion logs
aws logs tail /aws/lambda/noaa-ingest-atmospheric-dev \
  --follow --format short --profile noaa-target

# AI query logs
aws logs tail /aws/lambda/noaa-ai-query-dev \
  --follow --format short --profile noaa-target
```

### Query Data

```bash
# Count records
aws athena start-query-execution \
  --query-string "SELECT COUNT(*) FROM noaa_gold_dev.atmospheric" \
  --result-configuration "OutputLocation=s3://noaa-athena-results-899626030376-dev/" \
  --profile noaa-target

# Check recent data
aws athena start-query-execution \
  --query-string "SELECT * FROM noaa_gold_dev.atmospheric WHERE year=2024 AND month=12 ORDER BY observation_time DESC LIMIT 10" \
  --result-configuration "OutputLocation=s3://noaa-athena-results-899626030376-dev/" \
  --profile noaa-target
```

### Check System Status

```bash
# Lambda status
aws lambda list-functions \
  --query 'Functions[?contains(FunctionName, `noaa`)].FunctionName' \
  --profile noaa-target

# Glue job status
aws glue get-job-runs \
  --max-results 5 \
  --profile noaa-target \
  --query 'JobRuns[*].[JobName,JobRunState,StartedOn]' \
  --output table

# S3 bucket size
aws s3 ls s3://noaa-federated-lake-899626030376-dev/ \
  --recursive --summarize --human-readable --profile noaa-target
```

---

## 🚨 Alerts & Notifications

### Set Up Email Alerts

```bash
# Create SNS topic
aws sns create-topic --name noaa-alerts --profile noaa-target

# Subscribe your email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:899626030376:noaa-alerts \
  --protocol email \
  --notification-endpoint your-email@domain.com \
  --profile noaa-target

# Create alarm
aws cloudwatch put-metric-alarm \
  --alarm-name noaa-high-errors \
  --alarm-description "Alert on high error rate" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:899626030376:noaa-alerts \
  --profile noaa-target
```

---

## 📱 Mobile Access

Both CloudWatch and HTML dashboards are mobile-responsive:

1. **CloudWatch**: Use AWS Console mobile app
2. **HTML Dashboard**: Open in mobile browser

```bash
# Share dashboard via web server
cd monitoring
python3 -m http.server 8080

# Access from phone: http://your-ip:8080/dashboard_configured.html
```

---

## 🔐 Security

### CloudWatch Dashboards
- ✅ Uses IAM authentication
- ✅ No data stored locally
- ✅ Audit trail in CloudTrail

### HTML Dashboards
- ⚠️ Local files only (no server required)
- ⚠️ AWS credentials in localStorage (if configured)
- 💡 For production, use IAM roles instead

---

## 💰 Cost

### CloudWatch Dashboards
- **FREE** - Included with AWS account
- Up to 3 dashboards: $0/month
- Additional dashboards: $3/month each
- Metrics: First 10 custom metrics free

### HTML Dashboards
- **FREE** - No AWS charges
- Static HTML files
- No server required

**Total Monthly Cost: $0** ✨

---

## 🐛 Troubleshooting

### CloudWatch Dashboard Not Loading

```bash
# Verify AWS credentials
aws sts get-caller-identity --profile noaa-target

# List dashboards
aws cloudwatch list-dashboards --profile noaa-target --region us-east-1

# Re-deploy if needed
./deploy_dashboards.sh cloudwatch
```

### HTML Dashboard Shows No Data

**If using demo mode:**
- ✅ Expected - shows simulated data
- Click "Configure AWS Credentials" to connect to live data

**If configured with AWS:**
- Check AWS credentials in browser console (F12)
- Verify IAM permissions for CloudWatch read access

### Dashboards Show Old Data

```bash
# CloudWatch has eventual consistency
# Wait 1-2 minutes for latest data

# Force refresh in browser: Ctrl+F5 (Windows) or Cmd+Shift+R (Mac)
```

---

## 📚 Additional Resources

### Files in This Directory

- `deploy_dashboards.sh` - Main deployment script
- `create_cloudwatch_dashboards.sh` - CloudWatch-specific deployment
- `dashboard_configured.html` - Simple dashboard with links
- `dashboard_interactive.html` - Full interactive dashboard
- `open_dashboards.sh` - Quick launch script
- `README.md` - This file

### Related Documentation

- `../VISUALIZATION_GUIDE_NO_QUICKSIGHT.md` - Complete visualization guide
- `../ENHANCEMENTS_DEPLOYMENT_GUIDE.md` - Full system documentation
- `../config/environment.sh` - Configuration settings

### AWS Documentation

- [CloudWatch Dashboards](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Dashboards.html)
- [CloudWatch Metrics](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/working_with_metrics.html)
- [Athena Query](https://docs.aws.amazon.com/athena/latest/ug/what-is.html)

---

## 🎓 Next Steps

1. **Deploy Dashboards**
   ```bash
   ./deploy_dashboards.sh all
   ```

2. **Open and Explore**
   ```bash
   ./open_dashboards.sh
   ```

3. **Bookmark CloudWatch URLs**
   - Save dashboard links for quick access

4. **Set Up Alerts**
   - Configure SNS notifications
   - Create CloudWatch alarms

5. **Share with Team**
   - Email CloudWatch dashboard links
   - Host HTML dashboard on internal server

---

## 💡 Pro Tips

1. **Multiple Monitors**: Keep CloudWatch dashboard on second monitor
2. **Browser Tabs**: Pin CloudWatch tabs for quick access
3. **Bookmarks**: Save dashboard URLs in browser bookmarks bar
4. **Screenshots**: Use for status reports and presentations
5. **Auto-Refresh**: CloudWatch dashboards auto-refresh every 60 seconds

---

## 🆘 Support

### Questions?

1. Check the troubleshooting section above
2. Review `VISUALIZATION_GUIDE_NO_QUICKSIGHT.md`
3. Check AWS CloudWatch documentation
4. Review Lambda function logs

### Issues?

```bash
# Verify deployment
./deploy_dashboards.sh verify

# Re-deploy if needed
./deploy_dashboards.sh all
```

---

**Last Updated:** December 2024  
**Version:** 1.0  
**Maintained By:** NOAA Data Engineering Team

🌊 **Happy Monitoring!** 🌊
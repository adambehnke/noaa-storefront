# NOAA Visualization - Quick Start Guide

## 🚀 Get Started in 2 Minutes

### Step 1: Open Your Dashboards

```bash
cd monitoring
./open_dashboards.sh
```

This opens:
- ✅ Simple HTML Dashboard (links to CloudWatch)
- ✅ Interactive HTML Dashboard (live metrics)

---

## 📊 What You'll See

### HTML Dashboard (Immediately Available)

**Simple Dashboard** shows:
- 🏗️ System architecture overview
- 🔗 Direct links to all CloudWatch dashboards
- 💻 Quick commands for data queries
- 📚 Next steps checklist

**Interactive Dashboard** shows:
- 🌊 Live data flow: API → Bronze → Silver → Gold → Queries
- 📈 Real-time charts (updates every 60 seconds)
- 🤖 AI query interface demo
- ⚡ Performance metrics
- 📝 System logs

### CloudWatch Dashboards (In AWS Console)

Open these URLs:

**1. Data Ingestion Flow**
```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=NOAA-Data-Ingestion-Flow-dev
```
- Lambda invocations by pond
- Error rates
- Ingestion duration
- Success metrics

**2. System Health**
```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=NOAA-System-Health-dev
```
- Total records (24h)
- Error counts
- System health score
- Overall performance

**3. AI Query Processing**
```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=NOAA-AI-Query-Processing-dev
```
- Query volume
- Response times
- Success rates
- Athena performance

---

## 🎯 Daily Operations

### Morning Routine (5 minutes)

1. **Open System Health Dashboard**
   ```
   https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=NOAA-System-Health-dev
   ```

2. **Check Key Metrics:**
   - ✅ Error count should be near 0
   - ✅ Invocations should be ~900/day
   - ✅ No active alarms

3. **Bookmark for Quick Access**

### Monitor Throughout Day

1. **Keep Data Ingestion Dashboard Open**
   - Watch for error spikes
   - Monitor performance trends
   - Auto-refreshes every 60 seconds

2. **Check Interactive HTML Dashboard**
   ```bash
   open monitoring/dashboard_interactive.html
   ```
   - View live data flow
   - Check conversion rates
   - Monitor system logs

---

## 🔍 Key Metrics to Watch

### Critical (Check Daily)
- **Success Rate**: Should be > 99%
- **Ingestion Count**: ~937 invocations/day
- **Error Count**: Should be < 10/day
- **Conversion Rate**: Bronze → Gold > 95%

### Performance (Check Weekly)
- **Lambda Duration**: < 5 seconds average
- **Query Response**: < 5 seconds
- **Data Quality**: > 90% score
- **Storage Growth**: Monitor trends

---

## 🔧 Quick Commands

### View Live Logs
```bash
# Atmospheric ingestion
aws logs tail /aws/lambda/noaa-ingest-atmospheric-dev --follow --profile noaa-target

# AI queries
aws logs tail /aws/lambda/noaa-ai-query-dev --follow --profile noaa-target
```

### Query Your Data
```bash
# Count total records
aws athena start-query-execution \
  --query-string "SELECT COUNT(*) FROM noaa_gold_dev.atmospheric" \
  --result-configuration "OutputLocation=s3://noaa-athena-results-899626030376-dev/" \
  --profile noaa-target

# View recent data
aws athena start-query-execution \
  --query-string "SELECT * FROM noaa_gold_dev.atmospheric ORDER BY observation_time DESC LIMIT 10" \
  --result-configuration "OutputLocation=s3://noaa-athena-results-899626030376-dev/" \
  --profile noaa-target
```

### Check System Status
```bash
# List all Lambda functions
aws lambda list-functions --query 'Functions[?contains(FunctionName, `noaa`)].FunctionName' --profile noaa-target

# Check S3 storage
aws s3 ls s3://noaa-federated-lake-899626030376-dev/ --recursive --summarize --human-readable --profile noaa-target

# View Glue job runs
aws glue get-job-runs --max-results 5 --profile noaa-target --query 'JobRuns[*].[JobName,JobRunState]' --output table
```

---

## 🚨 Troubleshooting

### Dashboard Not Showing Data?

**CloudWatch Dashboard:**
1. Verify AWS credentials: `aws sts get-caller-identity --profile noaa-target`
2. Wait 1-2 minutes for metrics to appear
3. Force refresh: `Ctrl+F5` (Windows) or `Cmd+Shift+R` (Mac)

**HTML Dashboard:**
- Demo mode is normal (shows simulated data)
- Click "Configure AWS Credentials" to connect live data
- Or just use for architecture overview

### High Error Rate?

1. Open Data Ingestion Dashboard
2. Identify failing pond (red spikes)
3. Click Lambda function name
4. Check CloudWatch Logs
5. Fix API or Lambda issue

### No Recent Data?

1. Check Lambda invocations: Should run every 15 minutes
2. Verify EventBridge rules are enabled
3. Check NOAA API status
4. Review Lambda error logs

---

## 📱 Mobile Access

### CloudWatch
- Download "AWS Console" mobile app
- Sign in and navigate to CloudWatch → Dashboards
- View all metrics on mobile device

### HTML Dashboard
```bash
# Host on local network
cd monitoring
python3 -m http.server 8080

# Access from phone: http://your-ip:8080/dashboard_configured.html
```

---

## 🎓 Next Steps

### Today
- [ ] Bookmark CloudWatch dashboard URLs
- [ ] Open and explore HTML dashboards
- [ ] Run a few test queries
- [ ] Share dashboard links with team

### This Week
- [ ] Set up email alerts (see full guide)
- [ ] Schedule team training session
- [ ] Add to daily operations routine
- [ ] Document any issues found

### This Month
- [ ] Customize dashboards for your needs
- [ ] Create operational runbooks
- [ ] Optimize query performance
- [ ] Review cost trends

---

## 📚 Full Documentation

For complete details, see:

- **Full Guide**: `VISUALIZATION_GUIDE_NO_QUICKSIGHT.md` (986 lines)
- **Deployment**: `VISUALIZATION_DEPLOYED.md` (632 lines)
- **Monitoring README**: `monitoring/README.md` (522 lines)

---

## 💰 Cost Summary

| Component | Monthly Cost |
|-----------|-------------|
| CloudWatch Dashboards | FREE |
| HTML Dashboards | FREE |
| CloudWatch Logs | ~$5 |
| Athena Queries | ~$5 |
| **Total** | **~$10** |

**vs QuickSight**: $90/month (5 users)  
**Savings**: $80/month (88% less) ✨

---

## 🆘 Need Help?

### Quick Help
```bash
# Re-deploy dashboards
cd monitoring && ./deploy_dashboards.sh all

# Verify deployment
./deploy_dashboards.sh verify

# Open dashboards
./open_dashboards.sh
```

### Documentation
- Read: `monitoring/README.md`
- Full guide: `VISUALIZATION_GUIDE_NO_QUICKSIGHT.md`
- System status: `./verify_complete_system.sh`

---

## ✅ Success Checklist

- [x] ✅ HTML dashboards deployed and working
- [x] ✅ CloudWatch dashboards accessible
- [x] ✅ Quick launch script ready
- [x] ✅ Documentation complete
- [ ] ⏳ Bookmarks saved in browser
- [ ] ⏳ Team members have access
- [ ] ⏳ Email alerts configured
- [ ] ⏳ Daily check-in routine established

---

**🌊 You're all set! Start monitoring your NOAA Data Lake now. 🌊**

**Quick Access:**
```bash
cd monitoring && ./open_dashboards.sh
```

**CloudWatch:**
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:
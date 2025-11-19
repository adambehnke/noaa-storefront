# NOAA Data Lake Chatbot - Quick Deploy Reference

**⚡ 5-Minute AWS Deployment**

---

## Prerequisites Checklist

- [ ] AWS CLI installed and configured (`aws --version`)
- [ ] AWS account with admin access
- [ ] API Gateway URL from existing NOAA deployment

---

## One-Command Deployment

```bash
cd noaa_storefront/webapp && ./deploy-chatbot.sh
```

That's it! The script will:
1. Find your API Gateway URL
2. Deploy CloudFormation stack
3. Upload files to S3
4. Configure CloudFront CDN
5. Give you the website URL

**Time:** ~10 minutes

---

## Manual 3-Step Deployment

### Step 1: Update Config
```bash
# Edit app.js line 9
API_BASE_URL: 'https://YOUR-API-GATEWAY-URL.amazonaws.com/dev'
```

### Step 2: Deploy Stack
```bash
aws cloudformation deploy \
  --template-file deploy-to-aws.yaml \
  --stack-name noaa-chatbot-prod \
  --parameter-overrides \
      ApiGatewayUrl="YOUR-API-GATEWAY-URL" \
      EnableWAF=false \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

### Step 3: Upload Files
```bash
# Get bucket name
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name noaa-chatbot-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`WebsiteBucketName`].OutputValue' \
  --output text)

# Upload
aws s3 cp index.html s3://$BUCKET/ --cache-control "no-cache"
aws s3 cp app.js s3://$BUCKET/ --cache-control "max-age=31536000"

# Invalidate cache
DIST_ID=$(aws cloudformation describe-stacks \
  --stack-name noaa-chatbot-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
  --output text)

aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"
```

---

## Get Your Website URL

```bash
aws cloudformation describe-stacks \
  --stack-name noaa-chatbot-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`WebsiteURL`].OutputValue' \
  --output text
```

---

## Common Commands

### Update Deployment
```bash
./deploy-chatbot.sh
```

### View Logs
```bash
# CloudFront logs
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name noaa-chatbot-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`LoggingBucketName`].OutputValue' \
  --output text)

aws s3 ls s3://$BUCKET/cloudfront/
```

### Check Status
```bash
aws cloudformation describe-stacks \
  --stack-name noaa-chatbot-prod \
  --query 'Stacks[0].StackStatus'
```

### Delete Everything
```bash
aws cloudformation delete-stack --stack-name noaa-chatbot-prod
```

---

## Quick Troubleshooting

### Issue: "Website returns 403"
```bash
# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id $DIST_ID --paths "/*"
```

### Issue: "API calls failing"
```bash
# Verify API URL in app.js
grep "API_BASE_URL" app.js

# Test API Gateway
curl -X POST "YOUR-API-GATEWAY-URL/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

### Issue: "Stack creation failed"
```bash
# View errors
aws cloudformation describe-stack-events \
  --stack-name noaa-chatbot-prod \
  --max-items 10

# Delete and retry
aws cloudformation delete-stack --stack-name noaa-chatbot-prod
# Wait 5 minutes, then redeploy
```

---

## Cost Estimate

- **Without WAF:** ~$1-2/month
- **With WAF:** ~$7-8/month

Pricing based on 10K users/month

---

## Architecture

```
User → CloudFront → S3 (static HTML/JS)
       ↓
       JavaScript calls API Gateway
       ↓
       Lambda → NOAA APIs
```

---

## Testing Queries

After deployment, try these:

```
"Show me weather alerts in California"
"What are the tide levels in San Francisco?"
"Ocean buoy data near Boston"
"Historical temperature trends for Texas"
```

---

## Support

- **Full Docs:** `CHATBOT_AWS_DEPLOYMENT.md`
- **Webapp README:** `webapp/README.md`
- **System Status:** `SYSTEM_VALIDATION_REPORT.md`

---

## Key Files

| File | Purpose |
|------|---------|
| `deploy-chatbot.sh` | Automated deployment |
| `deploy-to-aws.yaml` | CloudFormation template |
| `app.js` | Chatbot JavaScript (update API URL) |
| `index.html` | Chatbot UI |

---

## What Gets Deployed

✅ S3 bucket (private)
✅ CloudFront distribution (global CDN)
✅ CloudWatch dashboard
✅ SNS alerts
✅ IAM roles
✅ Optional: WAF (DDoS protection)

---

## Environment Variables (Optional)

```bash
export AWS_REGION=us-east-1
export API_GATEWAY_URL="https://your-url.amazonaws.com/dev"
export ENABLE_WAF=false
```

---

## Success Checklist

After deployment, verify:

- [ ] Website loads at CloudFront URL
- [ ] Can submit queries in chatbot
- [ ] Receives responses from API
- [ ] Data displays correctly
- [ ] Theme toggle works
- [ ] Mobile responsive

---

## Production Checklist

Before going live:

- [ ] Enable WAF (`EnableWAF=true`)
- [ ] Set up custom domain
- [ ] Configure SNS alerts
- [ ] Enable CloudWatch alarms
- [ ] Review CORS settings
- [ ] Test from multiple regions
- [ ] Load test (optional)

---

## Quick Links

- **AWS Console:** https://console.aws.amazon.com/cloudformation
- **CloudFront Console:** https://console.aws.amazon.com/cloudfront
- **S3 Console:** https://console.aws.amazon.com/s3

---

**Status:** ✅ Production Ready
**Deploy Time:** 10 minutes
**Cost:** $1-8/month
**Scale:** Unlimited
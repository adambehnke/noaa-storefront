# 🚀 CloudFront Webapp Update - Fix "Loading..." Issue

## Problem
Your CloudFront deployment at `https://dq8oz5pgpnqc1.cloudfront.net/` is serving **old files** from S3 that don't include the endpoint fallback data fix.

**Symptoms:**
- "Loading endpoint information..." (never updates)
- "Endpoints: Loading..." in Service Status
- Console shows no errors but data never appears

## Solution
Update the deployed `app.js` file on S3 and invalidate the CloudFront cache.

---

## ⚡ Quick Fix (Automated)

### Step 1: Run the Update Script

```bash
cd noaa_storefront/webapp
./update_deployed_app.sh
```

This script will:
1. ✅ Find your CloudFormation stack and S3 bucket
2. ✅ Backup the current app.js
3. ✅ Upload the fixed app.js with fallback data
4. ✅ Upload index.html for compatibility
5. ✅ Invalidate CloudFront cache for `/app.js`, `/index.html`, and `/`

### Step 2: Wait for Invalidation (5-15 minutes)

CloudFront cache invalidation takes time. You can monitor progress:

```bash
# Get your distribution ID
aws cloudformation describe-stacks \
  --stack-name noaa-chatbot-prod \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
  --output text

# Check invalidation status (replace INVALIDATION_ID)
aws cloudfront get-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --id YOUR_INVALIDATION_ID
```

### Step 3: Verify the Fix

After 5-15 minutes:

1. Open **incognito/private window**: `https://dq8oz5pgpnqc1.cloudfront.net/`
2. **Force refresh**: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)
3. **Open browser console** (F12)
4. Look for: `✓ Using 6 data ponds: atmospheric, oceanic, buoy, climate, spatial, terrestrial`
5. **Click "Endpoints & Services"** - should show 40+ endpoints
6. **Click "Service Status"** - should show 6 active services with "Endpoints: 40"

✅ **Success**: No more "Loading..." - everything displays immediately!

---

## 🔧 Manual Fix (If Script Fails)

### Step 1: Find Your S3 Bucket

```bash
aws cloudformation describe-stacks \
  --stack-name noaa-chatbot-prod \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`WebsiteBucketName`].OutputValue' \
  --output text
```

Example output: `noaa-chatbot-prod-websitebucket-abc123xyz`

### Step 2: Upload Files to S3

```bash
cd noaa_storefront/webapp

# Upload app.js (with cache-control)
aws s3 cp app.js s3://YOUR-BUCKET-NAME/ \
  --content-type "application/javascript" \
  --cache-control "public, max-age=300" \
  --region us-east-1

# Upload index.html (no cache)
aws s3 cp index.html s3://YOUR-BUCKET-NAME/ \
  --content-type "text/html" \
  --cache-control "no-cache, no-store, must-revalidate" \
  --region us-east-1
```

### Step 3: Invalidate CloudFront Cache

```bash
# Get CloudFront Distribution ID
aws cloudformation describe-stacks \
  --stack-name noaa-chatbot-prod \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
  --output text

# Create invalidation
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/app.js" "/index.html" "/*"
```

### Step 4: Wait and Verify

Wait 5-15 minutes, then test in incognito mode with force refresh.

---

## 📋 What Changed in app.js

The updated `app.js` includes:

### 1. FALLBACK_PONDS Constant (Lines 32-108)

```javascript
const FALLBACK_PONDS = {
  atmospheric: {
    name: "Atmospheric",
    endpoints: [
      { name: "Active Alerts", service: "NWS", url: "/alerts/active" },
      { name: "Point Forecasts", service: "NWS", url: "/gridpoints" },
      // ... 6 more endpoints
    ]
  },
  oceanic: { /* 8 endpoints */ },
  buoy: { /* 5 endpoints */ },
  climate: { /* 7 endpoints */ },
  spatial: { /* 2 endpoints */ },
  terrestrial: { /* 3 endpoints */ }
};
// Total: 40+ endpoints across 6 ponds
```

### 2. Updated loadAvailablePonds() Function

```javascript
async function loadAvailablePonds() {
  let pondsData = null;
  
  try {
    // Try to fetch from API first
    const response = await fetch(API_URL);
    if (response.ok) {
      pondsData = await response.json();
    }
  } catch (error) {
    console.warn("API unavailable, using fallback");
  }
  
  // Use fallback if API failed
  if (!pondsData) {
    pondsData = FALLBACK_PONDS;
  }
  
  // ALWAYS update UI (this was missing before!)
  updatePondSelector(pondsData);
  updatePondServiceMapping(pondsData);
}
```

**Key Fix**: The function now ALWAYS updates the UI, whether using API data or fallback data.

---

## 🧪 Testing the Fix

### Test 1: Browser Console

Open DevTools console (F12) and look for:

```
✅ GOOD:
  Using fallback pond data
  ✓ Using 6 data ponds: atmospheric, oceanic, buoy, climate, spatial, terrestrial
  ✓ Populated 40 endpoints across 6 ponds
  ✓ Service status updated: 6 services, 40 endpoints across 6 ponds

❌ BAD (old version):
  Error loading ponds metadata: [error]
  [No follow-up messages]
```

### Test 2: UI Elements

**Endpoints & Services Section:**
- ✅ Shows 40+ endpoints organized by pond
- ✅ Each endpoint shows service badge (NWS, COOPS, NDBC, etc.)
- ❌ OLD: "Loading endpoint information..."

**Service Status Section:**
- ✅ Shows "6 Data Sources" and "40 Total Endpoints"
- ✅ Lists 6 services (NWS, COOPS, NDBC, CDO, NEXRAD, USGS)
- ✅ Footer shows "Endpoints: 40"
- ❌ OLD: "Endpoints: Loading..."

### Test 3: Network Tab

1. Open DevTools → Network tab
2. Refresh page
3. Find `app.js` request
4. Check **Response Headers**:
   - Should have recent `Last-Modified` date
   - Check file size (should be ~95KB with fallback data vs ~75KB without)

---

## 🚨 Troubleshooting

### Issue: Still Shows "Loading..." After Update

**Causes & Solutions:**

1. **CloudFront cache not invalidated yet**
   - Wait 5-15 minutes
   - Check invalidation status (see commands above)

2. **Browser cache not cleared**
   - Use incognito/private window
   - Clear browser cache completely
   - Force refresh: `Ctrl+Shift+R` / `Cmd+Shift+R`

3. **Wrong file uploaded**
   - Verify app.js has `FALLBACK_PONDS` constant
   ```bash
   grep "FALLBACK_PONDS" webapp/app.js
   # Should return: const FALLBACK_PONDS = {
   ```

4. **Old file still on S3**
   - Download from S3 and check:
   ```bash
   aws s3 cp s3://YOUR-BUCKET/app.js test_app.js
   grep "FALLBACK_PONDS" test_app.js
   ```

### Issue: Script Can't Find CloudFormation Stack

```bash
# List all stacks
aws cloudformation list-stacks \
  --region us-east-1 \
  --query 'StackSummaries[?StackStatus==`CREATE_COMPLETE` || StackStatus==`UPDATE_COMPLETE`].StackName'

# If stack name is different, update the script:
# Edit update_deployed_app.sh line 18:
STACK_NAME="your-actual-stack-name"
```

### Issue: No CloudFront Distribution

If you're using S3 static website hosting without CloudFront:

```bash
# Just upload to S3 (no invalidation needed)
aws s3 cp app.js s3://YOUR-BUCKET/ --region us-east-1
aws s3 cp index.html s3://YOUR-BUCKET/ --region us-east-1

# S3 will serve new version immediately
```

---

## ✅ Expected Results

### Before Fix:
```
Endpoints & Services:
  Loading endpoint information...

Service Status:
  NWS API [Active]
  NOAA Tides [Active]
  NDBC Buoys [Active]
  CDO Climate [Token Req]
  Endpoints: Loading...          ← STUCK HERE
```

### After Fix:
```
Endpoints & Services:
  🌤 ATMOSPHERIC (8 endpoints)
    • Active Alerts (NWS)
    • Point Forecasts (NWS)
    • Hourly Forecasts (NWS)
    [... 5 more]
  
  🌊 OCEANIC (8 endpoints)
    • Water Level (COOPS)
    • Predictions (COOPS)
    [... 6 more]
  
  [... 4 more ponds]

Service Status:
  6 Data Sources
  40 Total Endpoints
  
  NWS
  8 endpoints | ✓ Active
  
  COOPS
  8 endpoints | ✓ Active
  
  [... 4 more services]
  
  Endpoints: 40                  ← FIXED!
```

---

## 📞 Quick Reference

### Key Commands

```bash
# Deploy update
cd noaa_storefront/webapp && ./update_deployed_app.sh

# Check CloudFront invalidation
aws cloudfront list-invalidations --distribution-id YOUR_DIST_ID

# Verify file on S3
aws s3 cp s3://YOUR-BUCKET/app.js - | grep -c "FALLBACK_PONDS"
# Should output: 1

# Test locally first
cd noaa_storefront/webapp
python3 -m http.server 8080
# Visit: http://localhost:8080
```

### Key Files

- **Update script**: `webapp/update_deployed_app.sh`
- **Fixed app.js**: `webapp/app.js` (contains FALLBACK_PONDS)
- **Test page**: `webapp/test_endpoints.html`
- **This guide**: `webapp/CLOUDFRONT_UPDATE_INSTRUCTIONS.md`

---

## 🎯 Success Criteria

✅ Webapp loads in incognito mode  
✅ Browser console shows: `✓ Using 6 data ponds`  
✅ Endpoints section shows 40+ endpoints  
✅ Service Status shows 6 services  
✅ No "Loading..." text anywhere  
✅ Clicking endpoints shows "Querying endpoint..." message  

**Estimated Time**: 20 minutes (5 min upload + 15 min cache invalidation)

---

## 🚀 Next Steps After Fix

1. ✅ Verify webapp works with fallback data
2. 🔄 Deploy backend Lambda functions: `./scripts/master_deploy.sh --env dev --full-deploy`
3. 🔗 Update `CONFIG.API_BASE_URL` in app.js with your API Gateway endpoint
4. 📤 Deploy again with live API connection
5. 🎉 Enjoy real-time NOAA data!

---

**Last Updated**: November 13, 2024  
**Status**: Ready to deploy  
**Estimated Fix Time**: 20 minutes
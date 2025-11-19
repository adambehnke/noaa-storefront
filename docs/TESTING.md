# NOAA Federated Data Lake - Testing Guide

Comprehensive testing documentation for the NOAA Data Lake Chatbot webapp.

## Overview

This project uses **Puppeteer** (headless Chrome) for automated end-to-end testing without any manual intervention. The test suite validates the entire application stack from UI to API integration.

## CLI Browser Options

For testing web applications from the command line without a GUI, you have several options:

### 1. Puppeteer (Recommended) ✅

**Best for:** Node.js projects, fast execution, Chrome/Chromium-based testing

```bash
# Install
npm install puppeteer

# Run tests
node test_e2e_puppeteer.js
```

**Pros:**
- Comes bundled with Chromium
- Fast and reliable
- Excellent API
- Best integration with Node.js
- Active development by Google Chrome team

**Cons:**
- Chrome/Chromium only
- Larger installation size (~300MB)

### 2. Playwright

**Best for:** Cross-browser testing (Chrome, Firefox, Safari)

```bash
# Install
npm install playwright

# Run tests
npx playwright test
```

**Pros:**
- Multiple browser support
- Modern API similar to Puppeteer
- Built-in test runner
- Better mobile emulation

**Cons:**
- Larger installation
- More complex for simple projects

### 3. Selenium WebDriver

**Best for:** Legacy projects, specific browser versions

```bash
# Install
npm install selenium-webdriver

# Requires separate browser drivers
```

**Pros:**
- Industry standard
- Extensive language support
- Mature ecosystem

**Cons:**
- More complex setup
- Slower execution
- Requires separate driver management

### 4. lynx / w3m / links (Text-based browsers)

**Best for:** Basic HTTP testing, server-side rendering validation

```bash
# Install (macOS)
brew install lynx

# Test page load
lynx -dump http://localhost:8000
```

**Pros:**
- Extremely lightweight
- Fast
- No JavaScript required

**Cons:**
- No JavaScript execution
- No CSS rendering
- Limited interaction capabilities

## Quick Start

### 1. Install Dependencies

```bash
cd /Users/adambehnke/Projects/noaa_storefront
npm install
```

This installs Puppeteer and all required dependencies (~300MB download).

### 2. Run Tests

#### Test CloudFront Deployment (Production)
```bash
npm run test:cloudfront
```

#### Test Local Development Server
```bash
# Terminal 1: Start local server
npm run serve

# Terminal 2: Run tests
npm run test:local
```

#### Watch Tests Run (Visible Browser)
```bash
# Set headless to false to see the browser
HEADLESS=false node test_e2e_puppeteer.js https://d3m3e2kbgwdfko.cloudfront.net
```

#### Test Any URL
```bash
node test_e2e_puppeteer.js <URL>
```

## Test Coverage

The E2E test suite validates:

### ✅ Infrastructure & Deployment (Tests 1-2)
- Page loads successfully
- Correct page title
- Network requests complete
- No 404/500 errors

### ✅ DOM Structure (Test 3)
- All critical elements present:
  - Chat messages container
  - Chat input field
  - Send button
  - Sidebar
  - Pond selector
  - Service status panel

### ✅ JavaScript Initialization (Tests 4-5)
- No undefined variables
- No runtime errors
- Configuration objects loaded
- State management initialized
- Fallback data available

### ✅ Configuration (Test 6)
- API endpoints configured
- Base URLs correct
- Timeout settings appropriate
- Cache busting enabled

### ✅ Data Pond Configuration (Test 7)
- Pond selector populated
- All expected ponds available:
  - Atmospheric
  - Oceanic
  - Buoy
  - Climate
  - Spatial
  - Terrestrial
- "All Ponds" option present

### ✅ Service Status Display (Tests 8-9)
- Service status panel visible
- Service health indicators shown
- Endpoint availability displayed
- 30+ endpoints listed across ponds

### ✅ Chat Interface (Tests 10-12)
- Chat input enabled
- Send button functional
- Can type messages
- Can send messages
- Receives responses (if API available)
- Message history displayed

### ✅ Interactive Elements (Test 13)
- Pond selector changes
- Quick action buttons work
- Collapsible sections function

### ✅ UI Responsiveness (Test 14)
- Sidebar visible and functional
- Main content area displays
- Chat container responsive
- Layout adapts to content

### ✅ Console & Error Analysis (Test 15)
- No critical JavaScript errors
- Initialization messages logged
- No unexpected warnings
- Clean error state

### ✅ Visual Validation (Test 16)
- Screenshot capture
- Full-page rendering
- Element positioning

## Test Results

Expected output:
```
🚀 Starting NOAA Data Lake E2E Tests
Target URL: https://d3m3e2kbgwdfko.cloudfront.net
Timestamp: 2024-11-13T19:30:00.000Z

============================================================
1. Browser Initialization
============================================================
✓ Browser launched
✓ Page created with viewport 1920x1080

============================================================
2. Page Load & HTML Structure
============================================================
✓ PASS: Page loads successfully
✓ PASS: Page has correct title
✓ PASS: Element exists: chatMessages
✓ PASS: Element exists: chatInput
✓ PASS: Element exists: sendBtn
...

============================================================
TEST SUMMARY
============================================================
Total Tests:    35
Passed:         34
Failed:         1
Warnings:       1
Pass Rate:      97.1%

🎉 ALL CRITICAL TESTS PASSED!
```

## Troubleshooting

### Issue: "puppeteer: not found"

**Solution:**
```bash
npm install puppeteer
```

### Issue: "Failed to launch chrome"

**Solution (macOS):**
```bash
# Install required dependencies
xcode-select --install

# Or use system Chrome
npm install puppeteer-core
```

**Solution (Linux):**
```bash
# Install dependencies
sudo apt-get install -y \
  libnss3 \
  libatk-bridge2.0-0 \
  libgtk-3-0 \
  libgbm1
```

### Issue: "Timeout waiting for page load"

**Solution:**
```bash
# Increase timeout in test file or run with longer timeout
node test_e2e_puppeteer.js --timeout=60000
```

### Issue: Tests pass but chatbot doesn't respond

**Check:**
1. API Gateway is deployed and accessible
2. CORS is configured correctly
3. Lambda functions are running
4. API key/authentication is configured

```bash
# Test API directly
curl -X POST https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"test"}'
```

### Issue: "isResizing is not defined" error

**Fixed in version 3.4.2+**

If you see this error, make sure you have the latest `webapp/app.js`:
```bash
# Check version
grep "Version:" webapp/app.js

# Should show: Version: 3.4.2 or higher
```

## Alternative Testing Methods

### 1. CURL Testing (API Only)

```bash
# Test /ask endpoint
curl -X POST https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the current weather in Miami?",
    "pond": "atmospheric"
  }'
```

### 2. Python Requests (Scripted Testing)

```python
import requests

url = "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask"
data = {
    "question": "Show me buoy data near the Florida coast",
    "pond": "buoy"
}

response = requests.post(url, json=data)
print(response.json())
```

### 3. Browser DevTools (Manual Testing)

```javascript
// Open browser console on deployed page
// Run this to test chatbot programmatically
sendMessage("What weather data is available?");
```

### 4. Playwright (Alternative to Puppeteer)

If you prefer Playwright for cross-browser testing:

```bash
npm install @playwright/test
npx playwright test
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-node@v2
        with:
          node-version: '18'
      - run: npm install
      - run: npm run test:cloudfront
```

### GitLab CI Example

```yaml
test:
  image: node:18
  script:
    - npm install
    - npm run test:cloudfront
  artifacts:
    paths:
      - test-screenshot-*.png
```

## Performance Testing

### Load Testing with Artillery

```bash
npm install -g artillery

# Create artillery.yml
artillery run artillery.yml
```

```yaml
config:
  target: "https://d3m3e2kbgwdfko.cloudfront.net"
  phases:
    - duration: 60
      arrivalRate: 10
scenarios:
  - name: "Chat interaction"
    flow:
      - get:
          url: "/"
      - post:
          url: "https://u35c31x306.execute-api.us-east-1.amazonaws.com/dev/ask"
          json:
            question: "test"
            pond: "all"
```

## Best Practices

1. **Run tests before deployment:**
   ```bash
   npm test && npm run deploy
   ```

2. **Test both local and production:**
   ```bash
   npm run test:local && npm run test:cloudfront
   ```

3. **Keep screenshots for debugging:**
   - Screenshots saved as `test-screenshot-<timestamp>.png`
   - Useful for visual regression testing

4. **Monitor test execution time:**
   - Tests should complete in < 30 seconds
   - Slow tests indicate performance issues

5. **Review console logs:**
   - Check for warnings
   - Validate initialization messages
   - Monitor error patterns

## Support

For issues or questions:
1. Check this documentation
2. Review console logs in test output
3. Run with `HEADLESS=false` to watch browser
4. Check CloudFront/API Gateway logs
5. Validate app.js has no syntax errors

## Version History

- **v1.0.0** (2024-11-13): Initial Puppeteer test suite
- **v1.0.1** (2024-11-13): Fixed isResizing variable declaration
- **v1.0.2** (2024-11-13): Added comprehensive E2E tests

---

**Last Updated:** November 13, 2024  
**Maintained By:** NOAA Data Lake Team
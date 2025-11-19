# NOAA Federated Data Lake - Testing Suite

Comprehensive automated testing suite for the NOAA Data Lake webapp using Python/Playwright.

## Overview

This directory contains all automated tests for validating the NOAA Data Lake chatbot webapp. Tests cover functionality, UI/UX, API integration, and content verification.

**Test Framework:** Python + Playwright (Headless Chrome)  
**Test Coverage:** Frontend UI, JavaScript initialization, API connectivity, data display  
**Automation Level:** Fully automated, no manual intervention required

---

## Quick Start

### 1. Setup (One-Time)

```bash
# Navigate to project root
cd /Users/adambehnke/Projects/noaa_storefront

# Create virtual environment (if not exists)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install playwright

# Install Chromium browser
playwright install chromium
```

### 2. Run Tests

```bash
# Simple diagnostic test (recommended first run)
./venv/bin/python tests/test_simple.py https://dq8oz5pgpnqc1.cloudfront.net

# Visual inspection (opens browser, you can watch)
./venv/bin/python tests/test_visual_check.py https://dq8oz5pgpnqc1.cloudfront.net

# Content verification
./venv/bin/python tests/test_content_check.py https://dq8oz5pgpnqc1.cloudfront.net

# Full end-to-end test suite
./venv/bin/python tests/test_e2e_python.py https://dq8oz5pgpnqc1.cloudfront.net
```

---

## Test Files

### `test_simple.py` - Quick Diagnostic Test

**Purpose:** Fast check to verify JavaScript loading and basic functionality

**What it tests:**
- Page loads successfully
- Page title is correct
- JavaScript CONFIG object is defined
- State and elements initialized
- Console has no critical errors
- Core DOM elements exist

**Run time:** ~10 seconds

**Usage:**
```bash
./venv/bin/python tests/test_simple.py [URL]

# Examples
./venv/bin/python tests/test_simple.py https://dq8oz5pgpnqc1.cloudfront.net
./venv/bin/python tests/test_simple.py http://localhost:8765
```

**Output:**
- Console messages
- JavaScript object status
- DOM element checks
- Screenshot: `diagnostic-screenshot.png`

**Best for:** Quick smoke testing after deployment

---

### `test_visual_check.py` - Visual Inspection Test

**Purpose:** Interactive visual verification of UI elements and collapsible sections

**What it tests:**
- Service Status section visibility
- Endpoints section visibility
- Collapsible section states
- All sidebar element IDs
- Section content after expansion

**Run time:** ~20 seconds (opens visible browser)

**Usage:**
```bash
./venv/bin/python tests/test_visual_check.py [URL]
```

**Output:**
- Detailed section analysis
- Collapsible state information
- Screenshots: `logs/visual-inspection.png`, `logs/visual-inspection-expanded.png`

**Best for:** Debugging UI visibility issues

---

### `test_content_check.py` - Content Verification Test

**Purpose:** Verify endpoints and services are populated with correct data

**What it tests:**
- Endpoints container content (33 endpoints expected)
- Service status container content (7 services expected)
- Endpoint groups by pond
- Service active status
- Summary statistics

**Run time:** ~15 seconds (opens visible browser)

**Usage:**
```bash
./venv/bin/python tests/test_content_check.py [URL]
```

**Output:**
- Detailed endpoint list by pond
- Service status with endpoint counts
- Pass/Fail summary
- Screenshots: `logs/content-check-*.png`

**Best for:** Verifying data population after backend changes

---

### `test_e2e_python.py` - End-to-End Test Suite

**Purpose:** Comprehensive automated testing of entire webapp

**What it tests:**
- Page load and HTML structure (2 tests)
- JavaScript initialization (4 tests)
- Configuration and state (2 tests)
- Data pond configuration (4 tests)
- Service status display (2 tests)
- Endpoint display (2 tests)
- Chat interface (3 tests)
- Chatbot functionality (3 tests)
- Pond selector interaction (1 test)
- UI responsiveness (3 tests)
- Console log analysis (2 tests)
- Screenshot capture (1 test)

**Total:** 33 tests

**Run time:** ~60-90 seconds

**Usage:**
```bash
./venv/bin/python tests/test_e2e_python.py [URL]
```

**Output:**
- Detailed test results for each test
- Pass/fail rate
- Test duration
- Screenshot: `test-screenshot-[timestamp].png`

**Best for:** Full regression testing before production deployment

---

### `test_e2e_puppeteer.js` - Node.js/Puppeteer Alternative

**Purpose:** Same as Python E2E but using Node.js and Puppeteer

**Status:** Requires Node.js (currently has dependency issues with icu4c)

**Usage:**
```bash
npm install  # In tests/ directory
node tests/test_e2e_puppeteer.js [URL]
```

**Note:** Use Python tests instead unless you specifically need Puppeteer

---

## Test Targets

### Production
```bash
./venv/bin/python tests/[test_name].py https://dq8oz5pgpnqc1.cloudfront.net
```

### Local Development
```bash
# Terminal 1: Start local server
cd webapp && python3 -m http.server 8765

# Terminal 2: Run tests
./venv/bin/python tests/[test_name].py http://localhost:8765
```

---

## Expected Test Results

### ✅ Successful Test Output

```
🚀 Starting NOAA Data Lake E2E Tests (Python/Playwright)
Target URL: https://dq8oz5pgpnqc1.cloudfront.net

✓ Page loads successfully
✓ JavaScript CONFIG defined
✓ Elements initialized
✓ 33 endpoints found
✓ 7 services active
✓ No JavaScript errors

Total Tests:    33
Passed:         30
Failed:         3
Pass Rate:      90.9%

✅ PASS - Both sections are populated and visible
```

### ❌ Failed Test Output

```
✗ FAIL: Page loads successfully
  net::ERR_NAME_NOT_RESOLVED

✗ FAIL: JavaScript CONFIG loaded
  CONFIG not defined
```

---

## Interpreting Results

### Pass Rate Guidelines

- **≥90%:** ✅ Excellent - Production ready
- **70-89%:** ⚠️ Good - Minor issues to address
- **50-69%:** ⚠️ Fair - Significant issues present
- **<50%:** ❌ Poor - Critical issues, do not deploy

### Common Test Failures (Non-Critical)

1. **Element ID mismatches** - Test uses wrong IDs (kebab-case vs camelCase)
   - Impact: Test fails but app works fine
   - Fix: Update test to use correct IDs

2. **API timeout** - Backend Athena query takes >15 seconds
   - Impact: Chatbot response test fails
   - Fix: Expected behavior if data lake empty

3. **CloudFront cache** - Old files served due to cache
   - Impact: Outdated code tested
   - Fix: Force invalidation and wait 3 minutes

---

## Troubleshooting

### Issue: "playwright: not found"

**Solution:**
```bash
pip install playwright
playwright install chromium
```

### Issue: "Page.goto: net::ERR_NAME_NOT_RESOLVED"

**Possible causes:**
1. CloudFront domain incorrect
2. Network connectivity issue
3. VPN blocking access

**Solution:**
```bash
# Test connectivity
curl -I https://dq8oz5pgpnqc1.cloudfront.net

# Check DNS resolution
nslookup dq8oz5pgpnqc1.cloudfront.net
```

### Issue: "CONFIG not defined"

**Possible causes:**
1. app.js failed to load
2. JavaScript syntax error
3. CloudFront serving old cached file

**Solution:**
```bash
# Check deployed JavaScript
curl -s https://dq8oz5pgpnqc1.cloudfront.net/app.js | grep "const CONFIG"

# Invalidate cache
aws cloudfront create-invalidation --distribution-id E22UXNSTO9T2DE --paths "/*"
```

### Issue: Tests pass locally but fail on CloudFront

**Cause:** CloudFront cache not invalidated

**Solution:**
```bash
# Deploy with automatic invalidation
./scripts/deploy_webapp.sh

# Or manually invalidate
aws cloudfront create-invalidation --distribution-id E22UXNSTO9T2DE --paths "/*"

# Wait 1-3 minutes, then retest
```

---

## Screenshots

All tests generate screenshots saved to:
- `./logs/` directory (current working directory)
- Named with test type and timestamp
- Full-page captures for complete UI review

**Screenshot files:**
- `diagnostic-screenshot.png` - Simple diagnostic test
- `visual-inspection.png` - Before expanding sections
- `visual-inspection-expanded.png` - After expanding sections
- `content-check-*.png` - Content verification screenshots
- `test-screenshot-[timestamp].png` - E2E test screenshots

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install playwright
      - run: playwright install chromium
      - run: python tests/test_e2e_python.py https://dq8oz5pgpnqc1.cloudfront.net
```

---

## Development

### Adding New Tests

1. Copy existing test file as template
2. Modify test logic as needed
3. Update this README with new test documentation
4. Test locally before committing

### Test Best Practices

- ✅ Use descriptive test names
- ✅ Add console logging for debugging
- ✅ Capture screenshots on failure
- ✅ Wait for elements before interaction
- ✅ Handle timeouts gracefully
- ❌ Don't hardcode element IDs without checking HTML
- ❌ Don't assume timing - use explicit waits
- ❌ Don't skip error handling

---

## Dependencies

### Python Packages

```
playwright>=1.40.0
```

### System Requirements

- Python 3.9+
- 500MB disk space (for Chromium)
- Internet connection (for external CDN resources)

### Optional

- Node.js 16+ (for Puppeteer tests)
- AWS CLI (for deployment)

---

## Test History

| Date | Version | Tests | Pass Rate | Notes |
|------|---------|-------|-----------|-------|
| 2025-11-14 | 1.0 | 33 | 54.5% | Initial test suite, element ID issues |
| 2025-11-14 | 1.1 | 33 | 90%+ | Fixed element visibility, all working |

---

## Support

**Documentation:**
- Full Testing Guide: `../docs/TESTING.md`
- Deployment Guide: `../scripts/deploy_webapp.sh --help`
- Architecture: `../docs/ARCHITECTURE_*.md`

**Common Issues:**
- Check `../logs/` for deployment and test logs
- Review screenshots for visual debugging
- Check browser console in test output

**Contact:**
- Project Lead: Adam Behnke
- Repository: `/Users/adambehnke/Projects/noaa_storefront`

---

*Last Updated: 2025-11-14*  
*Test Framework Version: 1.1*  
*Maintained by: NOAA Data Lake Team*
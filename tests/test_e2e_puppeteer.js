/**
 * NOAA Federated Data Lake - End-to-End Puppeteer Tests
 * Comprehensive automated testing without human intervention
 *
 * Installation:
 *   npm install puppeteer
 *
 * Usage:
 *   node test_e2e_puppeteer.js [URL]
 *   node test_e2e_puppeteer.js https://d3m3e2kbgwdfko.cloudfront.net
 */

const puppeteer = require('puppeteer');

// Configuration
const CONFIG = {
  url: process.argv[2] || 'http://localhost:8000',
  headless: true,  // Set to false to see browser actions
  timeout: 30000,
  viewport: { width: 1920, height: 1080 },
  slowMo: 0  // Milliseconds to slow down Puppeteer operations (useful for debugging)
};

// Test results tracking
const results = {
  passed: 0,
  failed: 0,
  warnings: 0,
  tests: []
};

// Colors for terminal output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m'
};

// Utility functions
function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function logTest(name, passed, details = '') {
  const status = passed ? '✓ PASS' : '✗ FAIL';
  const color = passed ? 'green' : 'red';
  log(`${status}: ${name}`, color);
  if (details) {
    log(`  ${details}`, 'cyan');
  }
  results.tests.push({ name, passed, details });
  if (passed) results.passed++;
  else results.failed++;
}

function logWarning(message) {
  log(`⚠ WARNING: ${message}`, 'yellow');
  results.warnings++;
}

function logSection(title) {
  log(`\n${'='.repeat(60)}`, 'blue');
  log(title, 'bright');
  log('='.repeat(60), 'blue');
}

// Test Suite
async function runTests() {
  log('\n🚀 Starting NOAA Data Lake E2E Tests', 'bright');
  log(`Target URL: ${CONFIG.url}`, 'cyan');
  log(`Timestamp: ${new Date().toISOString()}\n`, 'cyan');

  let browser, page;
  const consoleMessages = [];
  const errors = [];

  try {
    // Launch browser
    logSection('1. Browser Initialization');
    browser = await puppeteer.launch({
      headless: CONFIG.headless,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-web-security'
      ]
    });
    log('✓ Browser launched', 'green');

    page = await browser.newPage();
    await page.setViewport(CONFIG.viewport);
    log('✓ Page created with viewport 1920x1080', 'green');

    // Capture console messages
    page.on('console', msg => {
      const text = msg.text();
      consoleMessages.push({ type: msg.type(), text });
      if (msg.type() === 'error') {
        errors.push(text);
      }
    });

    // Capture page errors
    page.on('pageerror', error => {
      errors.push(error.message);
    });

    // Test 1: Page Load
    logSection('2. Page Load & HTML Structure');
    try {
      await page.goto(CONFIG.url, {
        waitUntil: 'networkidle2',
        timeout: CONFIG.timeout
      });
      logTest('Page loads successfully', true, CONFIG.url);
    } catch (error) {
      logTest('Page loads successfully', false, error.message);
      throw error;
    }

    // Test 2: Page Title
    const title = await page.title();
    logTest('Page has correct title',
      title.includes('NOAA'),
      `Title: "${title}"`
    );

    // Test 3: Critical DOM Elements
    const elements = await page.evaluate(() => {
      return {
        chatMessages: !!document.getElementById('chat-messages'),
        chatInput: !!document.getElementById('chat-input'),
        sendBtn: !!document.getElementById('send-btn'),
        sidebar: !!document.getElementById('sidebar'),
        pondSelector: !!document.getElementById('pond-selector'),
        serviceStatus: !!document.getElementById('service-status')
      };
    });

    Object.entries(elements).forEach(([name, exists]) => {
      logTest(`Element exists: ${name}`, exists);
    });

    // Test 4: JavaScript Initialization
    logSection('3. JavaScript Initialization');
    await page.waitForTimeout(2000); // Wait for JS to initialize

    const jsInitialized = await page.evaluate(() => {
      return {
        configExists: typeof CONFIG !== 'undefined',
        stateExists: typeof state !== 'undefined',
        elementsExists: typeof elements !== 'undefined',
        fallbackPondsExists: typeof FALLBACK_PONDS !== 'undefined'
      };
    });

    Object.entries(jsInitialized).forEach(([name, exists]) => {
      logTest(`JS object initialized: ${name}`, exists);
    });

    // Test 5: No JavaScript Errors
    logSection('4. JavaScript Error Check');
    const jsErrors = errors.filter(e =>
      !e.includes('favicon') &&
      !e.includes('isResizing')
    );
    logTest('No critical JavaScript errors', jsErrors.length === 0,
      jsErrors.length > 0 ? `Found ${jsErrors.length} errors` : ''
    );

    if (jsErrors.length > 0) {
      jsErrors.slice(0, 5).forEach(err => {
        log(`  Error: ${err}`, 'red');
      });
    }

    // Test 6: Configuration Check
    logSection('5. Configuration & State');
    const config = await page.evaluate(() => {
      return {
        apiBaseUrl: CONFIG.API_BASE_URL,
        plaintextEndpoint: CONFIG.PLAINTEXT_ENDPOINT,
        passthroughEndpoint: CONFIG.PASSTHROUGH_ENDPOINT,
        version: typeof VERSION !== 'undefined' ? VERSION : 'unknown'
      };
    });

    logTest('API Base URL configured',
      !config.apiBaseUrl.includes('your-api-gateway'),
      config.apiBaseUrl
    );
    logTest('Plaintext endpoint configured',
      config.plaintextEndpoint === '/ask',
      config.plaintextEndpoint
    );

    // Test 7: Pond Data
    logSection('6. Data Pond Configuration');
    const pondData = await page.evaluate(() => {
      const pondOptions = document.querySelectorAll('#pond-selector option');
      const ponds = Array.from(pondOptions).map(opt => opt.value);
      return {
        count: ponds.length,
        ponds: ponds,
        hasAll: ponds.includes('all'),
        hasAtmospheric: ponds.includes('atmospheric'),
        hasOceanic: ponds.includes('oceanic')
      };
    });

    logTest('Pond selector populated',
      pondData.count >= 6,
      `Found ${pondData.count} ponds`
    );
    logTest('Has "All Ponds" option', pondData.hasAll);
    logTest('Has Atmospheric pond', pondData.hasAtmospheric);
    logTest('Has Oceanic pond', pondData.hasOceanic);

    log(`  Available ponds: ${pondData.ponds.join(', ')}`, 'cyan');

    // Test 8: Service Status
    logSection('7. Service Status Display');
    const serviceStatus = await page.evaluate(() => {
      const statusDiv = document.getElementById('service-status');
      if (!statusDiv) return { exists: false };

      const services = statusDiv.querySelectorAll('.service-item');
      return {
        exists: true,
        serviceCount: services.length,
        hasContent: statusDiv.textContent.trim().length > 0
      };
    });

    logTest('Service status panel exists', serviceStatus.exists);
    if (serviceStatus.exists) {
      logTest('Service status has content',
        serviceStatus.hasContent,
        `Found ${serviceStatus.serviceCount} services`
      );
    }

    // Test 9: Endpoint Display
    logSection('8. Endpoint Display');
    const endpoints = await page.evaluate(() => {
      const endpointDiv = document.getElementById('available-endpoints');
      if (!endpointDiv) return { exists: false };

      const items = endpointDiv.querySelectorAll('.endpoint-item');
      return {
        exists: true,
        count: items.length,
        hasContent: endpointDiv.textContent.trim().length > 0
      };
    });

    logTest('Endpoints panel exists', endpoints.exists);
    if (endpoints.exists) {
      logTest('Endpoints populated',
        endpoints.count >= 20,
        `Found ${endpoints.count} endpoints`
      );
    }

    // Test 10: Chat Input Functionality
    logSection('9. Chat Interface');
    const inputEnabled = await page.evaluate(() => {
      const input = document.getElementById('chat-input');
      const sendBtn = document.getElementById('send-btn');
      return {
        inputExists: !!input,
        inputEnabled: input && !input.disabled,
        sendBtnExists: !!sendBtn,
        sendBtnEnabled: sendBtn && !sendBtn.disabled
      };
    });

    logTest('Chat input exists and enabled', inputEnabled.inputExists && inputEnabled.inputEnabled);
    logTest('Send button exists and enabled', inputEnabled.sendBtnExists && inputEnabled.sendBtnEnabled);

    // Test 11: Quick Action Buttons
    const quickActions = await page.evaluate(() => {
      const buttons = document.querySelectorAll('.quick-action-btn');
      return {
        count: buttons.length,
        hasButtons: buttons.length > 0,
        buttons: Array.from(buttons).slice(0, 5).map(btn => btn.textContent.trim())
      };
    });

    logTest('Quick action buttons present',
      quickActions.count >= 5,
      `Found ${quickActions.count} buttons`
    );
    if (quickActions.buttons.length > 0) {
      log(`  Sample buttons: ${quickActions.buttons.join(', ')}`, 'cyan');
    }

    // Test 12: Send a Test Message
    logSection('10. Chatbot Functionality');
    try {
      // Type a test message
      await page.type('#chat-input', 'What weather data is available?');
      logTest('Can type in chat input', true);

      // Click send button
      await page.click('#send-btn');
      logTest('Can click send button', true);

      // Wait for response (or timeout)
      try {
        await page.waitForSelector('.assistant-message', { timeout: 15000 });
        logTest('Received chatbot response', true);
      } catch (e) {
        logWarning('No chatbot response within 15 seconds (API may be unavailable)');
        logTest('Received chatbot response', false, 'Timeout after 15s');
      }

      // Check message history
      await page.waitForTimeout(1000);
      const messageCount = await page.evaluate(() => {
        return document.querySelectorAll('.message').length;
      });
      logTest('Messages displayed in chat',
        messageCount >= 1,
        `Found ${messageCount} messages`
      );

    } catch (error) {
      logTest('Chat message sending', false, error.message);
    }

    // Test 13: Pond Selector Interaction
    logSection('11. Pond Selector Interaction');
    try {
      await page.select('#pond-selector', 'atmospheric');
      await page.waitForTimeout(500);

      const selectedPond = await page.evaluate(() => {
        return document.getElementById('pond-selector').value;
      });

      logTest('Can change pond selection',
        selectedPond === 'atmospheric',
        `Selected: ${selectedPond}`
      );
    } catch (error) {
      logTest('Can change pond selection', false, error.message);
    }

    // Test 14: Responsive Elements
    logSection('12. UI Responsiveness');
    const uiElements = await page.evaluate(() => {
      return {
        sidebarVisible: window.getComputedStyle(document.getElementById('sidebar')).display !== 'none',
        mainContentVisible: window.getComputedStyle(document.querySelector('.main-content')).display !== 'none',
        chatContainerVisible: window.getComputedStyle(document.querySelector('.chat-container')).display !== 'none'
      };
    });

    Object.entries(uiElements).forEach(([name, visible]) => {
      logTest(`UI element visible: ${name}`, visible);
    });

    // Test 15: Console Log Analysis
    logSection('13. Console Log Analysis');
    const initMessages = consoleMessages.filter(m =>
      m.text.includes('initialized') || m.text.includes('✓')
    );
    logTest('Initialization messages present',
      initMessages.length >= 5,
      `Found ${initMessages.length} init messages`
    );

    const errorMessages = consoleMessages.filter(m => m.type === 'error');
    const filteredErrors = errorMessages.filter(m =>
      !m.text.includes('favicon') &&
      !m.text.includes('isResizing')
    );
    logTest('No unexpected console errors',
      filteredErrors.length === 0,
      filteredErrors.length > 0 ? `${filteredErrors.length} errors found` : ''
    );

    // Test 16: Take Screenshot
    logSection('14. Screenshot Capture');
    try {
      const screenshotPath = `./test-screenshot-${Date.now()}.png`;
      await page.screenshot({
        path: screenshotPath,
        fullPage: true
      });
      logTest('Screenshot captured', true, screenshotPath);
    } catch (error) {
      logTest('Screenshot captured', false, error.message);
    }

  } catch (error) {
    log(`\n❌ Fatal Error: ${error.message}`, 'red');
    results.failed++;
  } finally {
    // Cleanup
    if (browser) {
      await browser.close();
      log('\n✓ Browser closed', 'green');
    }
  }

  // Print Summary
  printSummary();
}

function printSummary() {
  logSection('TEST SUMMARY');

  const total = results.passed + results.failed;
  const passRate = total > 0 ? ((results.passed / total) * 100).toFixed(1) : 0;

  log(`Total Tests:    ${total}`, 'cyan');
  log(`Passed:         ${results.passed}`, 'green');
  log(`Failed:         ${results.failed}`, results.failed > 0 ? 'red' : 'green');
  log(`Warnings:       ${results.warnings}`, 'yellow');
  log(`Pass Rate:      ${passRate}%`, passRate >= 90 ? 'green' : passRate >= 70 ? 'yellow' : 'red');

  // Status indicator
  if (results.failed === 0) {
    log('\n🎉 ALL TESTS PASSED!', 'green');
  } else if (passRate >= 70) {
    log('\n⚠️  TESTS COMPLETED WITH FAILURES', 'yellow');
  } else {
    log('\n❌ TESTS FAILED', 'red');
  }

  // Failed tests detail
  if (results.failed > 0) {
    log('\nFailed Tests:', 'red');
    results.tests
      .filter(t => !t.passed)
      .forEach(t => {
        log(`  - ${t.name}`, 'red');
        if (t.details) log(`    ${t.details}`, 'cyan');
      });
  }

  log(`\nTest completed at: ${new Date().toISOString()}`, 'cyan');

  // Exit with appropriate code
  process.exit(results.failed > 0 ? 1 : 0);
}

// Run tests
runTests().catch(error => {
  log(`\n💥 Unhandled Error: ${error.message}`, 'red');
  console.error(error);
  process.exit(1);
});

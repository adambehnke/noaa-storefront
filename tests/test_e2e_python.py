#!/usr/bin/env python3
"""
NOAA Federated Data Lake - End-to-End Playwright Tests (Python)
Comprehensive automated testing without human intervention

Installation:
    pip install playwright
    playwright install chromium

Usage:
    python test_e2e_python.py [URL]
    python test_e2e_python.py https://d3m3e2kbgwdfko.cloudfront.net
    python test_e2e_python.py http://localhost:8000
"""

import json
import sys
import time
from datetime import datetime

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

# Configuration
CONFIG = {
    "url": sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000",
    "headless": True,  # Set to False to see browser actions
    "timeout": 30000,
    "viewport": {"width": 1920, "height": 1080},
    "slow_mo": 0,  # Milliseconds to slow down operations
}

# Test results tracking
results = {
    "passed": 0,
    "failed": 0,
    "warnings": 0,
    "tests": [],
    "start_time": None,
    "end_time": None,
}

# Console messages and errors
console_messages = []
errors = []


# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BRIGHT = "\033[1m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"


def log(message, color="RESET"):
    """Print colored log message"""
    color_code = getattr(Colors, color.upper(), Colors.RESET)
    print(f"{color_code}{message}{Colors.RESET}")


def log_test(name, passed, details=""):
    """Log test result"""
    status = "✓ PASS" if passed else "✗ FAIL"
    color = "GREEN" if passed else "RED"
    log(f"{status}: {name}", color)
    if details:
        log(f"  {details}", "CYAN")

    results["tests"].append({"name": name, "passed": passed, "details": details})
    if passed:
        results["passed"] += 1
    else:
        results["failed"] += 1


def log_warning(message):
    """Log warning message"""
    log(f"⚠ WARNING: {message}", "YELLOW")
    results["warnings"] += 1


def log_section(title):
    """Print section header"""
    log(f"\n{'=' * 60}", "BLUE")
    log(title, "BRIGHT")
    log("=" * 60, "BLUE")


def run_tests():
    """Main test runner"""
    results["start_time"] = datetime.now()

    log("\n🚀 Starting NOAA Data Lake E2E Tests (Python/Playwright)", "BRIGHT")
    log(f"Target URL: {CONFIG['url']}", "CYAN")
    log(f"Timestamp: {results['start_time'].isoformat()}\n", "CYAN")

    with sync_playwright() as p:
        try:
            # Launch browser
            log_section("1. Browser Initialization")
            browser = p.chromium.launch(
                headless=CONFIG["headless"], slow_mo=CONFIG["slow_mo"]
            )
            log("✓ Browser launched", "GREEN")

            context = browser.new_context(viewport=CONFIG["viewport"])
            page = context.new_page()
            log("✓ Page created with viewport 1920x1080", "GREEN")

            # Capture console messages
            def handle_console(msg):
                console_messages.append({"type": msg.type, "text": msg.text})
                if msg.type == "error":
                    errors.append(msg.text)

            page.on("console", handle_console)

            # Capture page errors
            def handle_error(error):
                errors.append(str(error))

            page.on("pageerror", handle_error)

            # Test 1: Page Load
            log_section("2. Page Load & HTML Structure")
            try:
                # Clear cache and navigate with proper wait
                context.clear_cookies()
                page.goto(CONFIG["url"], wait_until="load", timeout=CONFIG["timeout"])
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_load_state("networkidle")
                log_test("Page loads successfully", True, CONFIG["url"])
            except Exception as e:
                log_test("Page loads successfully", False, str(e))
                raise

            # Test 2: Page Title
            title = page.title()
            log_test("Page has correct title", "NOAA" in title, f'Title: "{title}"')

            # Test 3: Critical DOM Elements
            elements = page.evaluate("""() => {
                return {
                    chatMessages: !!document.getElementById('chat-messages'),
                    chatInput: !!document.getElementById('chat-input'),
                    sendBtn: !!document.getElementById('send-btn'),
                    sidebar: !!document.getElementById('sidebar'),
                    pondSelector: !!document.getElementById('pond-selector'),
                    serviceStatus: !!document.getElementById('service-status')
                };
            }""")

            for name, exists in elements.items():
                log_test(f"Element exists: {name}", exists)

            # Test 4: JavaScript Initialization
            log_section("3. JavaScript Initialization")
            page.wait_for_timeout(
                5000
            )  # Wait for JS to initialize (increased from 2s to 5s)

            js_initialized = page.evaluate("""() => {
                return {
                    configExists: typeof CONFIG !== 'undefined',
                    stateExists: typeof state !== 'undefined',
                    elementsExists: typeof elements !== 'undefined',
                    fallbackPondsExists: typeof FALLBACK_PONDS !== 'undefined'
                };
            }""")

            for name, exists in js_initialized.items():
                log_test(f"JS object initialized: {name}", exists)

            # Test 5: No JavaScript Errors
            log_section("4. JavaScript Error Check")
            js_errors = [
                e
                for e in errors
                if "favicon" not in e.lower() and "isresizing" not in e.lower()
            ]
            log_test(
                "No critical JavaScript errors",
                len(js_errors) == 0,
                f"Found {len(js_errors)} errors" if js_errors else "",
            )

            if js_errors:
                for err in js_errors[:5]:
                    log(f"  Error: {err}", "RED")

            # Test 6: Configuration Check
            log_section("5. Configuration & State")
            try:
                config = page.evaluate("""() => {
                    if (typeof CONFIG === 'undefined') {
                        return { error: 'CONFIG not defined', apiBaseUrl: 'undefined', plaintextEndpoint: 'undefined', passthroughEndpoint: 'undefined' };
                    }
                    return {
                        apiBaseUrl: CONFIG.API_BASE_URL,
                        plaintextEndpoint: CONFIG.PLAINTEXT_ENDPOINT,
                        passthroughEndpoint: CONFIG.PASSTHROUGH_ENDPOINT
                    };
                }""")

                if "error" in config:
                    log_test("JavaScript CONFIG loaded", False, config["error"])
                else:
                    log_test("JavaScript CONFIG loaded", True)
                    log_test(
                        "API Base URL configured",
                        "your-api-gateway" not in config["apiBaseUrl"],
                        config["apiBaseUrl"],
                    )
                    log_test(
                        "Plaintext endpoint configured",
                        config["plaintextEndpoint"] == "/ask",
                        config["plaintextEndpoint"],
                    )
            except Exception as e:
                log_test("Configuration check", False, str(e))

            # Test 7: Pond Data
            log_section("6. Data Pond Configuration")
            try:
                pond_data = page.evaluate("""() => {
                const pondOptions = document.querySelectorAll('#pond-selector option');
                const ponds = Array.from(pondOptions).map(opt => opt.value);
                return {
                    count: ponds.length,
                    ponds: ponds,
                    hasAll: ponds.includes('all'),
                    hasAtmospheric: ponds.includes('atmospheric'),
                    hasOceanic: ponds.includes('oceanic')
                };
            }""")

                log_test(
                    "Pond selector populated",
                    pond_data["count"] >= 6,
                    f"Found {pond_data['count']} ponds",
                )
                log_test('Has "All Ponds" option', pond_data["hasAll"])
                log_test("Has Atmospheric pond", pond_data["hasAtmospheric"])
                log_test("Has Oceanic pond", pond_data["hasOceanic"])

                log(f"  Available ponds: {', '.join(pond_data['ponds'])}", "CYAN")
            except Exception as e:
                log_test("Pond data evaluation", False, str(e))
                pond_data = {
                    "count": 0,
                    "hasAll": False,
                    "hasAtmospheric": False,
                    "hasOceanic": False,
                }

            # Test 8: Service Status
            log_section("7. Service Status Display")
            service_status = page.evaluate("""() => {
                const statusDiv = document.getElementById('service-status');
                if (!statusDiv) return { exists: false };

                const services = statusDiv.querySelectorAll('.service-item');
                return {
                    exists: true,
                    serviceCount: services.length,
                    hasContent: statusDiv.textContent.trim().length > 0
                };
            }""")

            log_test("Service status panel exists", service_status["exists"])
            if service_status["exists"]:
                log_test(
                    "Service status has content",
                    service_status["hasContent"],
                    f"Found {service_status['serviceCount']} services",
                )

            # Test 9: Endpoint Display
            log_section("8. Endpoint Display")
            endpoints = page.evaluate("""() => {
                const endpointDiv = document.getElementById('available-endpoints');
                if (!endpointDiv) return { exists: false };

                const items = endpointDiv.querySelectorAll('.endpoint-item');
                return {
                    exists: true,
                    count: items.length,
                    hasContent: endpointDiv.textContent.trim().length > 0
                };
            }""")

            log_test("Endpoints panel exists", endpoints["exists"])
            if endpoints["exists"]:
                log_test(
                    "Endpoints populated",
                    endpoints["count"] >= 20,
                    f"Found {endpoints['count']} endpoints",
                )

            # Test 10: Chat Input Functionality
            log_section("9. Chat Interface")
            input_enabled = page.evaluate("""() => {
                const input = document.getElementById('chat-input');
                const sendBtn = document.getElementById('send-btn');
                return {
                    inputExists: !!input,
                    inputEnabled: input && !input.disabled,
                    sendBtnExists: !!sendBtn,
                    sendBtnEnabled: sendBtn && !sendBtn.disabled
                };
            }""")

            log_test(
                "Chat input exists and enabled",
                input_enabled["inputExists"] and input_enabled["inputEnabled"],
            )
            log_test(
                "Send button exists and enabled",
                input_enabled["sendBtnExists"] and input_enabled["sendBtnEnabled"],
            )

            # Test 11: Quick Action Buttons
            quick_actions = page.evaluate("""() => {
                const buttons = document.querySelectorAll('.quick-action-btn');
                return {
                    count: buttons.length,
                    hasButtons: buttons.length > 0,
                    buttons: Array.from(buttons).slice(0, 5).map(btn => btn.textContent.trim())
                };
            }""")

            log_test(
                "Quick action buttons present",
                quick_actions["count"] >= 5,
                f"Found {quick_actions['count']} buttons",
            )
            if quick_actions["buttons"]:
                log(f"  Sample buttons: {', '.join(quick_actions['buttons'])}", "CYAN")

            # Test 12: Send a Test Message
            log_section("10. Chatbot Functionality")
            try:
                # Type a test message
                page.fill("#chat-input", "What weather data is available?")
                log_test("Can type in chat input", True)

                # Click send button
                page.click("#send-btn")
                log_test("Can click send button", True)

                # Wait for response (or timeout)
                try:
                    page.wait_for_selector(".assistant-message", timeout=15000)
                    log_test("Received chatbot response", True)
                except PlaywrightTimeout:
                    log_warning(
                        "No chatbot response within 15 seconds (API may be unavailable)"
                    )
                    log_test("Received chatbot response", False, "Timeout after 15s")

                # Check message history
                page.wait_for_timeout(1000)
                message_count = page.evaluate("""() => {
                    return document.querySelectorAll('.message').length;
                }""")
                log_test(
                    "Messages displayed in chat",
                    message_count >= 1,
                    f"Found {message_count} messages",
                )

            except Exception as e:
                log_test("Chat message sending", False, str(e))

            # Test 13: Pond Selector Interaction
            log_section("11. Pond Selector Interaction")
            try:
                page.select_option("#pond-selector", "atmospheric")
                page.wait_for_timeout(500)

                selected_pond = page.evaluate("""() => {
                    return document.getElementById('pond-selector').value;
                }""")

                log_test(
                    "Can change pond selection",
                    selected_pond == "atmospheric",
                    f"Selected: {selected_pond}",
                )
            except Exception as e:
                log_test("Can change pond selection", False, str(e))

            # Test 14: Responsive Elements
            log_section("12. UI Responsiveness")
            ui_elements = page.evaluate("""() => {
                return {
                    sidebarVisible: window.getComputedStyle(document.getElementById('sidebar')).display !== 'none',
                    mainContentVisible: window.getComputedStyle(document.querySelector('.main-content')).display !== 'none',
                    chatContainerVisible: window.getComputedStyle(document.querySelector('.chat-container')).display !== 'none'
                };
            }""")

            for name, visible in ui_elements.items():
                log_test(f"UI element visible: {name}", visible)

            # Test 15: Console Log Analysis
            log_section("13. Console Log Analysis")
            init_messages = [
                m
                for m in console_messages
                if "initialized" in m["text"].lower() or "✓" in m["text"]
            ]
            log_test(
                "Initialization messages present",
                len(init_messages) >= 5,
                f"Found {len(init_messages)} init messages",
            )

            filtered_errors = [
                m
                for m in console_messages
                if m["type"] == "error"
                and "favicon" not in m["text"].lower()
                and "isresizing" not in m["text"].lower()
            ]
            log_test(
                "No unexpected console errors",
                len(filtered_errors) == 0,
                f"{len(filtered_errors)} errors found" if filtered_errors else "",
            )

            # Test 16: Take Screenshot
            log_section("14. Screenshot Capture")
            try:
                screenshot_path = f"./test-screenshot-{int(time.time())}.png"
                page.screenshot(path=screenshot_path, full_page=True)
                log_test("Screenshot captured", True, screenshot_path)
            except Exception as e:
                log_test("Screenshot captured", False, str(e))

            # Cleanup
            browser.close()
            log("\n✓ Browser closed", "GREEN")

        except Exception as e:
            log(f"\n❌ Fatal Error: {str(e)}", "RED")
            results["failed"] += 1
            import traceback

            traceback.print_exc()

    results["end_time"] = datetime.now()
    print_summary()


def print_summary():
    """Print test summary"""
    log_section("TEST SUMMARY")

    total = results["passed"] + results["failed"]
    pass_rate = (results["passed"] / total * 100) if total > 0 else 0

    log(f"Total Tests:    {total}", "CYAN")
    log(f"Passed:         {results['passed']}", "GREEN")
    log(
        f"Failed:         {results['failed']}",
        "RED" if results["failed"] > 0 else "GREEN",
    )
    log(f"Warnings:       {results['warnings']}", "YELLOW")
    log(
        f"Pass Rate:      {pass_rate:.1f}%",
        "GREEN" if pass_rate >= 90 else "YELLOW" if pass_rate >= 70 else "RED",
    )

    # Execution time
    if results["start_time"] and results["end_time"]:
        duration = (results["end_time"] - results["start_time"]).total_seconds()
        log(f"Duration:       {duration:.2f} seconds", "CYAN")

    # Status indicator
    if results["failed"] == 0:
        log("\n🎉 ALL TESTS PASSED!", "GREEN")
    elif pass_rate >= 70:
        log("\n⚠️  TESTS COMPLETED WITH FAILURES", "YELLOW")
    else:
        log("\n❌ TESTS FAILED", "RED")

    # Failed tests detail
    if results["failed"] > 0:
        log("\nFailed Tests:", "RED")
        for test in results["tests"]:
            if not test["passed"]:
                log(f"  - {test['name']}", "RED")
                if test["details"]:
                    log(f"    {test['details']}", "CYAN")

    log(f"\nTest completed at: {results['end_time'].isoformat()}", "CYAN")

    # Exit with appropriate code
    sys.exit(0 if results["failed"] == 0 else 1)


if __name__ == "__main__":
    try:
        run_tests()
    except KeyboardInterrupt:
        log("\n\n⚠️  Tests interrupted by user", "YELLOW")
        sys.exit(130)
    except Exception as e:
        log(f"\n💥 Unhandled Error: {str(e)}", "RED")
        import traceback

        traceback.print_exc()
        sys.exit(1)

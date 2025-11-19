#!/usr/bin/env python3
"""
Simple diagnostic test to check JavaScript loading
Usage: python test_simple.py [URL]
"""

import sys

from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765"

print(f"\n🔍 Testing: {url}\n")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=500)
    page = browser.new_page()

    # Capture all console messages
    console_messages = []

    def log_console(msg):
        console_messages.append(f"[{msg.type}] {msg.text}")
        print(f"  Console [{msg.type}]: {msg.text}")

    page.on("console", log_console)

    # Capture errors
    errors = []

    def log_error(err):
        errors.append(str(err))
        print(f"  ❌ Page Error: {err}")

    page.on("pageerror", log_error)

    # Load page
    print("Loading page...")
    page.goto(url, wait_until="networkidle", timeout=30000)
    print("✓ Page loaded\n")

    # Wait a bit for JS to execute
    print("Waiting 3 seconds for JavaScript initialization...")
    page.wait_for_timeout(3000)

    # Check title
    title = page.title()
    print(f"\n📄 Page Title: {title}")

    # Check if CONFIG is defined
    print("\n🔧 Checking JavaScript objects...")
    result = page.evaluate("""() => {
        return {
            configDefined: typeof CONFIG !== 'undefined',
            stateDefined: typeof state !== 'undefined',
            elementsDefined: typeof elements !== 'undefined',
            configValue: typeof CONFIG !== 'undefined' ? CONFIG.API_BASE_URL : 'undefined',
            windowLoaded: document.readyState,
            scriptsCount: document.scripts.length,
            scripts: Array.from(document.scripts).map(s => s.src || 'inline')
        };
    }""")

    print(f"  CONFIG defined: {result['configDefined']}")
    print(f"  state defined: {result['stateDefined']}")
    print(f"  elements defined: {result['elementsDefined']}")
    print(f"  Document state: {result['windowLoaded']}")
    print(f"  Scripts loaded: {result['scriptsCount']}")
    print(f"  Script sources: {result['scripts']}")

    if result["configDefined"]:
        print(f"  API_BASE_URL: {result['configValue']}")

    # Check for critical elements
    print("\n🎯 Checking DOM elements...")
    elements_check = page.evaluate("""() => {
        return {
            chatMessages: !!document.getElementById('chat-messages'),
            chatInput: !!document.getElementById('chat-input'),
            sendBtn: !!document.getElementById('send-btn'),
            sidebar: !!document.getElementById('sidebar'),
            pondSelector: !!document.getElementById('pond-selector')
        };
    }""")

    for name, exists in elements_check.items():
        symbol = "✓" if exists else "✗"
        print(f"  {symbol} {name}: {exists}")

    # Summary
    print(f"\n📊 Console Messages: {len(console_messages)}")
    print(f"📊 Errors: {len(errors)}")

    if errors:
        print("\n❌ Errors found:")
        for err in errors[:5]:
            print(f"  - {err}")

    if not result["configDefined"]:
        print("\n⚠️  WARNING: JavaScript CONFIG not loaded!")
        print("   This usually means app.js failed to load or execute.")
        print("   Check:")
        print("   1. Is app.js in the same directory as index.html?")
        print("   2. Does app.js have syntax errors?")
        print("   3. Is the file path correct in index.html?")

    # Take screenshot
    screenshot_path = "./diagnostic-screenshot.png"
    page.screenshot(path=screenshot_path, full_page=True)
    print(f"\n📸 Screenshot saved: {screenshot_path}")

    # Keep browser open for 5 seconds so you can see it
    print("\nKeeping browser open for 5 seconds...")
    page.wait_for_timeout(5000)

    browser.close()
    print("\n✅ Test complete\n")

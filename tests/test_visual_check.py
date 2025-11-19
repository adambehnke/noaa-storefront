#!/usr/bin/env python3
"""
Visual inspection script to check what's actually displaying on the remote site
Usage: python test_visual_check.py [URL]
"""

import sys

from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else "https://dq8oz5pgpnqc1.cloudfront.net"

print(f"\n🔍 Visual Inspection: {url}\n")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=1000)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})

    # Capture console
    console_messages = []

    def log_console(msg):
        console_messages.append(f"[{msg.type}] {msg.text}")
        if "endpoint" in msg.text.lower() or "service" in msg.text.lower():
            print(f"  📋 Console: {msg.text}")

    page.on("console", log_console)

    # Load page
    print("Loading page...")
    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(5000)  # Wait for JS initialization
    print("✓ Page loaded\n")

    # Check service status section
    print("═" * 70)
    print("SERVICE STATUS SECTION")
    print("═" * 70)

    service_status = page.evaluate("""() => {
        const section = document.getElementById('service-status');
        if (!section) return { exists: false };

        return {
            exists: true,
            visible: window.getComputedStyle(section).display !== 'none',
            innerHTML: section.innerHTML.substring(0, 500),
            textContent: section.textContent.trim().substring(0, 500),
            childCount: section.children.length,
            classes: section.className,
            serviceItems: Array.from(section.querySelectorAll('.service-item')).map(item => ({
                text: item.textContent.trim(),
                visible: window.getComputedStyle(item).display !== 'none'
            }))
        };
    }""")

    if service_status["exists"]:
        print(f"✓ Service Status section EXISTS")
        print(f"  Visible: {service_status['visible']}")
        print(f"  Classes: {service_status['classes']}")
        print(f"  Child elements: {service_status['childCount']}")
        print(f"  Service items found: {len(service_status['serviceItems'])}")

        if service_status["serviceItems"]:
            print(f"\n  Service Items:")
            for i, item in enumerate(service_status["serviceItems"][:5], 1):
                print(f"    {i}. {item['text'][:100]} (visible: {item['visible']})")
        else:
            print(f"\n  ⚠️  No service items found!")
            print(f"  Text content: {service_status['textContent'][:200]}")
    else:
        print("✗ Service Status section NOT FOUND")

    # Check endpoints section
    print("\n" + "═" * 70)
    print("ENDPOINTS SECTION")
    print("═" * 70)

    endpoints = page.evaluate("""() => {
        const section = document.getElementById('available-endpoints');
        if (!section) return { exists: false };

        return {
            exists: true,
            visible: window.getComputedStyle(section).display !== 'none',
            innerHTML: section.innerHTML.substring(0, 500),
            textContent: section.textContent.trim().substring(0, 500),
            childCount: section.children.length,
            classes: section.className,
            endpointItems: Array.from(section.querySelectorAll('.endpoint-item')).map(item => ({
                text: item.textContent.trim(),
                visible: window.getComputedStyle(item).display !== 'none',
                classes: item.className
            }))
        };
    }""")

    if endpoints["exists"]:
        print(f"✓ Endpoints section EXISTS")
        print(f"  Visible: {endpoints['visible']}")
        print(f"  Classes: {endpoints['classes']}")
        print(f"  Child elements: {endpoints['childCount']}")
        print(f"  Endpoint items found: {len(endpoints['endpointItems'])}")

        if endpoints["endpointItems"]:
            print(f"\n  Endpoint Items:")
            for i, item in enumerate(endpoints["endpointItems"][:10], 1):
                print(f"    {i}. {item['text'][:80]} (visible: {item['visible']})")
        else:
            print(f"\n  ⚠️  No endpoint items found!")
            print(f"  Text content: {endpoints['textContent'][:200]}")
    else:
        print("✗ Endpoints section NOT FOUND")

    # Check collapsible sections
    print("\n" + "═" * 70)
    print("COLLAPSIBLE SECTIONS")
    print("═" * 70)

    collapsible = page.evaluate("""() => {
        const headers = document.querySelectorAll('.collapsible-header');
        return Array.from(headers).map(header => {
            const section = header.nextElementSibling;
            return {
                title: header.textContent.trim(),
                isCollapsed: header.classList.contains('collapsed'),
                sectionVisible: section ? window.getComputedStyle(section).display !== 'none' : false,
                sectionMaxHeight: section ? window.getComputedStyle(section).maxHeight : 'N/A'
            };
        });
    }""")

    if collapsible:
        print(f"Found {len(collapsible)} collapsible sections:")
        for i, section in enumerate(collapsible, 1):
            status = "COLLAPSED" if section["isCollapsed"] else "EXPANDED"
            print(f"  {i}. {section['title']}")
            print(f"     Status: {status}")
            print(f"     Section visible: {section['sectionVisible']}")
            print(f"     Max height: {section['sectionMaxHeight']}")
    else:
        print("No collapsible sections found")

    # Check all IDs in sidebar
    print("\n" + "═" * 70)
    print("ALL SIDEBAR IDS")
    print("═" * 70)

    sidebar_ids = page.evaluate("""() => {
        const sidebar = document.getElementById('sidebar');
        if (!sidebar) return [];

        const elements = sidebar.querySelectorAll('[id]');
        return Array.from(elements).map(el => ({
            id: el.id,
            tag: el.tagName.toLowerCase(),
            visible: window.getComputedStyle(el).display !== 'none',
            text: el.textContent.trim().substring(0, 50)
        }));
    }""")

    if sidebar_ids:
        print(f"Found {len(sidebar_ids)} elements with IDs in sidebar:")
        for item in sidebar_ids:
            vis = "✓" if item["visible"] else "✗"
            print(f"  {vis} #{item['id']} <{item['tag']}> - {item['text'][:40]}")
    else:
        print("No elements with IDs found in sidebar")

    # Take screenshot
    print("\n" + "═" * 70)
    screenshot_path = "./logs/visual-inspection.png"
    page.screenshot(path=screenshot_path, full_page=True)
    print(f"📸 Screenshot saved: {screenshot_path}")

    # Try clicking collapsible headers to expand
    print("\n" + "═" * 70)
    print("ATTEMPTING TO EXPAND COLLAPSIBLE SECTIONS")
    print("═" * 70)

    collapsed_headers = page.query_selector_all(".collapsible-header.collapsed")
    print(f"Found {len(collapsed_headers)} collapsed sections")

    for i, header in enumerate(collapsed_headers, 1):
        header_text = header.text_content().strip()
        print(f"  {i}. Clicking: {header_text}")
        header.click()
        page.wait_for_timeout(500)

    page.wait_for_timeout(2000)

    # Re-check after expanding
    print("\n" + "═" * 70)
    print("AFTER EXPANDING")
    print("═" * 70)

    service_status_after = page.evaluate("""() => {
        const section = document.getElementById('service-status');
        if (!section) return null;
        return {
            visible: window.getComputedStyle(section).display !== 'none',
            itemCount: section.querySelectorAll('.service-item').length
        };
    }""")

    endpoints_after = page.evaluate("""() => {
        const section = document.getElementById('available-endpoints');
        if (!section) return null;
        return {
            visible: window.getComputedStyle(section).display !== 'none',
            itemCount: section.querySelectorAll('.endpoint-item').length
        };
    }""")

    if service_status_after:
        print(
            f"Service Status: {service_status_after['itemCount']} items (visible: {service_status_after['visible']})"
        )

    if endpoints_after:
        print(
            f"Endpoints: {endpoints_after['itemCount']} items (visible: {endpoints_after['visible']})"
        )

    # Final screenshot after expanding
    screenshot_path_expanded = "./logs/visual-inspection-expanded.png"
    page.screenshot(path=screenshot_path_expanded, full_page=True)
    print(f"📸 Expanded screenshot: {screenshot_path_expanded}")

    print("\nKeeping browser open for 10 seconds...")
    page.wait_for_timeout(10000)

    browser.close()
    print("\n✅ Inspection complete\n")

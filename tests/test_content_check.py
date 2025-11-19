#!/usr/bin/env python3
"""
Detailed content checker for endpoints and services sections
Usage: python test_content_check.py [URL]
"""

import json
import sys

from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else "https://dq8oz5pgpnqc1.cloudfront.net"

print(f"\n{'=' * 80}")
print(f"NOAA Data Lake - Content Verification Test")
print(f"{'=' * 80}")
print(f"Testing: {url}\n")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=500)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})

    # Load page
    print("Loading page and waiting for initialization...")
    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(5000)
    print("✓ Page loaded\n")

    # Get detailed endpoint content
    print("=" * 80)
    print("ENDPOINTS CONTAINER CONTENT")
    print("=" * 80)

    endpoints_data = page.evaluate("""() => {
        const container = document.getElementById('endpoints-container');
        if (!container) return { error: 'Container not found' };

        const visible = window.getComputedStyle(container).display !== 'none';
        const maxHeight = window.getComputedStyle(container).maxHeight;

        // Get all endpoint items
        const endpointGroups = container.querySelectorAll('.endpoint-group');
        const groups = [];

        endpointGroups.forEach(group => {
            const pondName = group.querySelector('.pond-name')?.textContent.trim();
            const endpoints = [];

            group.querySelectorAll('.endpoint-item').forEach(item => {
                endpoints.push({
                    name: item.querySelector('.endpoint-name')?.textContent.trim(),
                    service: item.querySelector('.endpoint-service')?.textContent.trim(),
                    visible: window.getComputedStyle(item).display !== 'none'
                });
            });

            groups.push({
                pond: pondName,
                endpointCount: endpoints.length,
                endpoints: endpoints.slice(0, 5) // First 5 endpoints
            });
        });

        return {
            visible: visible,
            maxHeight: maxHeight,
            innerHTML: container.innerHTML.substring(0, 1000),
            textContent: container.textContent.trim().substring(0, 500),
            groupCount: groups.length,
            groups: groups,
            totalEndpoints: Array.from(container.querySelectorAll('.endpoint-item')).length
        };
    }""")

    if "error" in endpoints_data:
        print(f"✗ ERROR: {endpoints_data['error']}")
    else:
        print(f"Container Status:")
        print(f"  Visible: {endpoints_data['visible']}")
        print(f"  Max Height: {endpoints_data['maxHeight']}")
        print(f"  Total Groups: {endpoints_data['groupCount']}")
        print(f"  Total Endpoints: {endpoints_data['totalEndpoints']}")
        print()

        if endpoints_data["groups"]:
            print(f"Endpoint Groups Found:")
            for i, group in enumerate(endpoints_data["groups"], 1):
                print(f"\n  {i}. {group['pond']} ({group['endpointCount']} endpoints)")
                for j, ep in enumerate(group["endpoints"], 1):
                    vis = "✓" if ep["visible"] else "✗"
                    print(f"     {vis} {j}. {ep['name']} - {ep['service']}")
        else:
            print("\n⚠️  No endpoint groups found!")
            print(f"\nRaw text content (first 500 chars):")
            print(f"{endpoints_data['textContent']}")

    # Get detailed service status content
    print("\n" + "=" * 80)
    print("SERVICE STATUS CONTAINER CONTENT")
    print("=" * 80)

    services_data = page.evaluate("""() => {
        const container = document.getElementById('services-status-container');
        if (!container) return { error: 'Container not found' };

        const visible = window.getComputedStyle(container).display !== 'none';
        const maxHeight = window.getComputedStyle(container).maxHeight;

        // Get service items
        const serviceItems = container.querySelectorAll('.service-item');
        const services = [];

        serviceItems.forEach(item => {
            const name = item.querySelector('.service-name')?.textContent.trim();
            const status = item.querySelector('.service-status')?.textContent.trim();
            const endpoints = item.querySelector('.service-endpoints')?.textContent.trim();

            services.push({
                name: name || item.textContent.trim().split('\\n')[0],
                status: status,
                endpoints: endpoints,
                visible: window.getComputedStyle(item).display !== 'none'
            });
        });

        // Also check for any summary text
        const summaryDivs = container.querySelectorAll('div[style*="display: flex"]');
        const summaryItems = [];

        summaryDivs.forEach(div => {
            const text = div.textContent.trim();
            if (text) {
                summaryItems.push(text);
            }
        });

        return {
            visible: visible,
            maxHeight: maxHeight,
            innerHTML: container.innerHTML.substring(0, 1000),
            textContent: container.textContent.trim().substring(0, 500),
            serviceCount: services.length,
            services: services,
            summaryItems: summaryItems.slice(0, 10)
        };
    }""")

    if "error" in services_data:
        print(f"✗ ERROR: {services_data['error']}")
    else:
        print(f"Container Status:")
        print(f"  Visible: {services_data['visible']}")
        print(f"  Max Height: {services_data['maxHeight']}")
        print(f"  Total Services: {services_data['serviceCount']}")
        print()

        if services_data["services"]:
            print(f"Services Found:")
            for i, svc in enumerate(services_data["services"], 1):
                vis = "✓" if svc["visible"] else "✗"
                print(f"  {vis} {i}. {svc['name']}")
                if svc["status"]:
                    print(f"       Status: {svc['status']}")
                if svc["endpoints"]:
                    print(f"       Endpoints: {svc['endpoints']}")

        if services_data["summaryItems"]:
            print(f"\nSummary Items Found:")
            for i, item in enumerate(services_data["summaryItems"], 1):
                print(f"  {i}. {item}")

        if not services_data["services"] and not services_data["summaryItems"]:
            print("\n⚠️  No service items or summary found!")
            print(f"\nRaw text content (first 500 chars):")
            print(f"{services_data['textContent']}")

    # Check console messages
    print("\n" + "=" * 80)
    print("CONSOLE MESSAGES (Related to endpoints/services)")
    print("=" * 80)

    console_check = page.evaluate("""() => {
        // This won't get historical console logs, but let's check state
        return {
            stateExists: typeof state !== 'undefined',
            availablePonds: typeof availablePonds !== 'undefined' ? availablePonds : null,
            fallbackPondsExists: typeof FALLBACK_PONDS !== 'undefined'
        };
    }""")

    print(f"State Check:")
    print(f"  state exists: {console_check['stateExists']}")
    print(f"  FALLBACK_PONDS exists: {console_check['fallbackPondsExists']}")
    if console_check["availablePonds"]:
        print(
            f"  availablePonds: {json.dumps(console_check['availablePonds'], indent=4)}"
        )

    # Take screenshots
    print("\n" + "=" * 80)
    print("SCREENSHOTS")
    print("=" * 80)

    # Full page
    page.screenshot(path="./logs/content-check-full.png", full_page=True)
    print("✓ Full page: ./logs/content-check-full.png")

    # Just the sidebar
    sidebar = page.query_selector("#sidebar")
    if sidebar:
        sidebar.screenshot(path="./logs/content-check-sidebar.png")
        print("✓ Sidebar: ./logs/content-check-sidebar.png")

    # Endpoints section
    endpoints_el = page.query_selector("#endpoints-container")
    if endpoints_el:
        endpoints_el.screenshot(path="./logs/content-check-endpoints.png")
        print("✓ Endpoints: ./logs/content-check-endpoints.png")

    # Services section
    services_el = page.query_selector("#services-status-container")
    if services_el:
        services_el.screenshot(path="./logs/content-check-services.png")
        print("✓ Services: ./logs/content-check-services.png")

    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)

    # Summary
    endpoints_ok = (
        endpoints_data.get("totalEndpoints", 0) > 0
        if "error" not in endpoints_data
        else False
    )
    services_ok = (
        (
            services_data.get("serviceCount", 0) > 0
            or len(services_data.get("summaryItems", [])) > 0
        )
        if "error" not in services_data
        else False
    )

    print(f"\nEndpoints Section:")
    if endpoints_ok:
        print(f"  ✓ POPULATED - {endpoints_data['totalEndpoints']} endpoints found")
    else:
        print(f"  ✗ EMPTY or NOT FOUND")

    print(f"\nServices Section:")
    if services_ok:
        svc_count = services_data.get("serviceCount", 0)
        summary_count = len(services_data.get("summaryItems", []))
        print(f"  ✓ POPULATED - {svc_count} services, {summary_count} summary items")
    else:
        print(f"  ✗ EMPTY or NOT FOUND")

    print(f"\nOverall Status:")
    if endpoints_ok and services_ok:
        print(f"  ✅ PASS - Both sections are populated and visible")
    elif endpoints_ok or services_ok:
        print(f"  ⚠️  PARTIAL - Only one section is populated")
    else:
        print(f"  ❌ FAIL - Neither section is populated")

    print("\nKeeping browser open for 5 seconds for visual inspection...")
    page.wait_for_timeout(5000)

    browser.close()
    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80 + "\n")

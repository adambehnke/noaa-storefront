#!/usr/bin/env python3
"""
NOAA Webapp Console Simulation Test
Simulates browser loading and checks for JavaScript errors
"""

import json
import re
import sys
import urllib.error
import urllib.request
from typing import Dict, List, Tuple

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


class WebappTester:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.errors = []
        self.warnings = []
        self.passed = []

    def fetch_url(self, url: str) -> Tuple[str, int]:
        """Fetch URL and return content and status code"""
        try:
            req = urllib.request.Request(url)
            req.add_header(
                "User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read().decode("utf-8"), response.status
        except urllib.error.HTTPError as e:
            return "", e.code
        except Exception as e:
            self.errors.append(f"Failed to fetch {url}: {str(e)}")
            return "", 0

    def test_html_load(self) -> bool:
        """Test if HTML loads correctly"""
        print(f"\n{BLUE}[TEST 1]{RESET} Loading HTML page...")

        html, status = self.fetch_url(self.base_url)

        if status != 200:
            self.errors.append(f"HTML load failed with status {status}")
            print(f"  {RED}✗ Failed (Status: {status}){RESET}")
            return False

        if len(html) < 100:
            self.errors.append("HTML content too short")
            print(f"  {RED}✗ Failed (Empty response){RESET}")
            return False

        self.passed.append("HTML loads successfully")
        print(f"  {GREEN}✓ Passed (Size: {len(html)} bytes){RESET}")
        return True

    def test_javascript_load(self) -> Tuple[bool, str]:
        """Test if JavaScript file loads and has correct structure"""
        print(f"\n{BLUE}[TEST 2]{RESET} Loading JavaScript file...")

        js_url = f"{self.base_url}/app.js"
        js_content, status = self.fetch_url(js_url)

        if status != 200:
            self.errors.append(f"JavaScript load failed with status {status}")
            print(f"  {RED}✗ Failed (Status: {status}){RESET}")
            return False, ""

        if len(js_content) < 1000:
            self.errors.append("JavaScript content too short")
            print(f"  {RED}✗ Failed (Empty or truncated){RESET}")
            return False, ""

        self.passed.append("JavaScript loads successfully")
        print(f"  {GREEN}✓ Passed (Size: {len(js_content)} bytes){RESET}")
        return True, js_content

    def test_xml_tags(self, js_content: str) -> bool:
        """Check for XML tags that shouldn't be in JavaScript"""
        print(f"\n{BLUE}[TEST 3]{RESET} Checking for XML/HTML tags in JavaScript...")

        xml_patterns = [
            r"<text\b",
            r"</text>",
            r"<old_text",
            r"</old_text>",
            r"<html",
            r"<!DOCTYPE",
            r"<head>",
            r"<body>",
        ]

        found_issues = []
        for pattern in xml_patterns:
            matches = re.finditer(pattern, js_content, re.IGNORECASE)
            for match in matches:
                line_num = js_content[: match.start()].count("\n") + 1
                found_issues.append(f"Found '{match.group()}' at line {line_num}")

        if found_issues:
            for issue in found_issues:
                self.errors.append(f"XML/HTML tag in JavaScript: {issue}")
                print(f"  {RED}✗ {issue}{RESET}")
            return False

        self.passed.append("No XML/HTML tags found in JavaScript")
        print(f"  {GREEN}✓ Passed (No XML/HTML tags found){RESET}")
        return True

    def test_syntax_patterns(self, js_content: str) -> bool:
        """Check for common syntax issues"""
        print(f"\n{BLUE}[TEST 4]{RESET} Checking JavaScript syntax patterns...")

        issues = []

        # Check for mismatched braces
        open_braces = js_content.count("{")
        close_braces = js_content.count("}")
        if open_braces != close_braces:
            issues.append(
                f"Mismatched braces: {open_braces} open vs {close_braces} close"
            )

        # Check for mismatched brackets
        open_brackets = js_content.count("[")
        close_brackets = js_content.count("]")
        if open_brackets != close_brackets:
            issues.append(
                f"Mismatched brackets: {open_brackets} open vs {close_brackets} close"
            )

        # Check for mismatched parentheses
        open_parens = js_content.count("(")
        close_parens = js_content.count(")")
        if open_parens != close_parens:
            issues.append(
                f"Mismatched parentheses: {open_parens} open vs {close_parens} close"
            )

        # Check for common typos
        if re.search(r"function\s+function\s+", js_content):
            issues.append("Duplicate 'function' keyword found")

        if re.search(r"const\s+const\s+", js_content):
            issues.append("Duplicate 'const' keyword found")

        # Check for unterminated strings (basic check)
        lines = js_content.split("\n")
        for i, line in enumerate(lines):
            # Skip comments
            if "//" in line:
                line = line[: line.index("//")]
            if "/*" in line or "*/" in line:
                continue

            # Count quotes
            single_quotes = line.count("'") - line.count("\\'")
            double_quotes = line.count('"') - line.count('\\"')

            if single_quotes % 2 != 0 or double_quotes % 2 != 0:
                if not line.strip().startswith("//") and not line.strip().startswith(
                    "*"
                ):
                    issues.append(f"Possible unterminated string at line {i + 1}")

        if issues:
            for issue in issues:
                self.errors.append(f"Syntax issue: {issue}")
                print(f"  {RED}✗ {issue}{RESET}")
            return False

        self.passed.append("No syntax pattern issues detected")
        print(f"  {GREEN}✓ Passed{RESET}")
        print(f"    - Braces: {open_braces} pairs matched")
        print(f"    - Brackets: {open_brackets} pairs matched")
        print(f"    - Parentheses: {open_parens} pairs matched")
        return True

    def test_required_structures(self, js_content: str) -> bool:
        """Check for required JavaScript structures"""
        print(f"\n{BLUE}[TEST 5]{RESET} Checking for required structures...")

        required = {
            "CONFIG": r"const\s+CONFIG\s*=\s*{",
            "FALLBACK_PONDS": r"const\s+FALLBACK_PONDS\s*=\s*{",
            "state": r"const\s+state\s*=\s*{",
            "initializeElements": r"function\s+initializeElements\s*\(",
            "loadAvailablePonds": r"async\s+function\s+loadAvailablePonds\s*\(",
            "DOMContentLoaded": r"DOMContentLoaded",
        }

        missing = []
        for name, pattern in required.items():
            if not re.search(pattern, js_content):
                missing.append(name)

        if missing:
            for item in missing:
                self.errors.append(f"Missing required structure: {item}")
                print(f"  {RED}✗ Missing: {item}{RESET}")
            return False

        self.passed.append("All required structures present")
        print(f"  {GREEN}✓ Passed (All {len(required)} structures found){RESET}")
        for name in required.keys():
            print(f"    - {name}")
        return True

    def test_fallback_data(self, js_content: str) -> bool:
        """Validate fallback pond data structure"""
        print(f"\n{BLUE}[TEST 6]{RESET} Validating FALLBACK_PONDS data...")

        # Extract FALLBACK_PONDS content
        match = re.search(
            r"const\s+FALLBACK_PONDS\s*=\s*({.*?^};)",
            js_content,
            re.MULTILINE | re.DOTALL,
        )
        if not match:
            self.errors.append("Could not extract FALLBACK_PONDS")
            print(f"  {RED}✗ Failed (Cannot find FALLBACK_PONDS){RESET}")
            return False

        ponds_content = match.group(1)

        # Check for required ponds
        required_ponds = [
            "atmospheric",
            "oceanic",
            "buoy",
            "climate",
            "spatial",
            "terrestrial",
        ]
        missing_ponds = []

        for pond in required_ponds:
            if f"{pond}:" not in ponds_content and f'"{pond}":' not in ponds_content:
                missing_ponds.append(pond)

        if missing_ponds:
            for pond in missing_ponds:
                self.errors.append(f"Missing pond in FALLBACK_PONDS: {pond}")
                print(f"  {RED}✗ Missing pond: {pond}{RESET}")
            return False

        # Count endpoints
        endpoint_count = ponds_content.count("{ name:") + ponds_content.count("{name:")

        self.passed.append(f"FALLBACK_PONDS contains all {len(required_ponds)} ponds")
        print(f"  {GREEN}✓ Passed{RESET}")
        print(f"    - Ponds: {len(required_ponds)}")
        print(f"    - Endpoints: ~{endpoint_count}")
        return True

    def test_api_endpoint(self) -> bool:
        """Test if API endpoint is reachable"""
        print(f"\n{BLUE}[TEST 7]{RESET} Testing API Gateway endpoint...")

        # First get the API URL from JavaScript
        js_content, _ = self.fetch_url(f"{self.base_url}/app.js")

        api_match = re.search(r'API_BASE_URL:\s*["\']([^"\']+)["\']', js_content)
        if not api_match:
            self.warnings.append("Could not find API_BASE_URL in JavaScript")
            print(f"  {YELLOW}⚠ Skipped (API URL not found){RESET}")
            return True

        api_url = api_match.group(1)
        print(f"    Found API: {api_url}")

        # Test a simple query
        try:
            data = json.dumps({"query": "test"}).encode("utf-8")
            req = urllib.request.Request(f"{api_url}/ask", data=data)
            req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode("utf-8"))

                if "success" in result or "answer" in result:
                    self.passed.append("API endpoint is reachable and responding")
                    print(f"  {GREEN}✓ Passed (API responding){RESET}")
                    return True
                else:
                    self.warnings.append("API responded but with unexpected format")
                    print(f"  {YELLOW}⚠ Warning (Unexpected response format){RESET}")
                    return True

        except Exception as e:
            self.warnings.append(f"API test failed: {str(e)}")
            print(f"  {YELLOW}⚠ Warning (API not accessible: {str(e)}){RESET}")
            return True

    def test_cloudfront_cache(self) -> bool:
        """Check CloudFront cache headers"""
        print(f"\n{BLUE}[TEST 8]{RESET} Checking CloudFront cache configuration...")

        try:
            req = urllib.request.Request(f"{self.base_url}/app.js")
            with urllib.request.urlopen(req) as response:
                headers = response.headers

                cache_control = headers.get("Cache-Control", "Not set")
                age = headers.get("Age", "Not set")

                print(f"    Cache-Control: {cache_control}")
                print(f"    Age: {age}")

                if (
                    "no-cache" in cache_control.lower()
                    or "must-revalidate" in cache_control.lower()
                ):
                    self.passed.append("Cache control properly configured")
                    print(f"  {GREEN}✓ Passed (Cache properly configured){RESET}")
                else:
                    self.warnings.append("Cache control may cause stale content")
                    print(f"  {YELLOW}⚠ Warning (Check cache settings){RESET}")

                return True

        except Exception as e:
            self.warnings.append(f"Could not check cache headers: {str(e)}")
            print(f"  {YELLOW}⚠ Warning (Could not check headers){RESET}")
            return True

    def generate_report(self) -> Dict:
        """Generate final test report"""
        print(f"\n{BLUE}{'=' * 70}{RESET}")
        print(f"{BLUE}TEST SUMMARY{RESET}")
        print(f"{BLUE}{'=' * 70}{RESET}\n")

        total_tests = len(self.passed) + len(self.errors)
        passed_count = len(self.passed)
        failed_count = len(self.errors)
        warning_count = len(self.warnings)

        pass_rate = (passed_count / total_tests * 100) if total_tests > 0 else 0

        print(f"Total Tests:   {total_tests}")
        print(f"{GREEN}Passed:        {passed_count}{RESET}")
        print(f"{RED}Failed:        {failed_count}{RESET}")
        print(f"{YELLOW}Warnings:      {warning_count}{RESET}")
        print(f"Success Rate:  {pass_rate:.1f}%\n")

        if self.passed:
            print(f"{GREEN}✓ Passed Tests:{RESET}")
            for test in self.passed:
                print(f"  • {test}")
            print()

        if self.errors:
            print(f"{RED}✗ Failed Tests:{RESET}")
            for error in self.errors:
                print(f"  • {error}")
            print()

        if self.warnings:
            print(f"{YELLOW}⚠ Warnings:{RESET}")
            for warning in self.warnings:
                print(f"  • {warning}")
            print()

        if failed_count == 0:
            print(f"{GREEN}{'=' * 70}{RESET}")
            print(f"{GREEN}✅ ALL TESTS PASSED!{RESET}")
            print(f"{GREEN}{'=' * 70}{RESET}\n")
        else:
            print(f"{RED}{'=' * 70}{RESET}")
            print(f"{RED}❌ SOME TESTS FAILED{RESET}")
            print(f"{RED}{'=' * 70}{RESET}\n")

        return {
            "total": total_tests,
            "passed": passed_count,
            "failed": failed_count,
            "warnings": warning_count,
            "pass_rate": pass_rate,
            "success": failed_count == 0,
        }

    def run_all_tests(self) -> bool:
        """Run all tests"""
        print(f"{BLUE}{'=' * 70}{RESET}")
        print(f"{BLUE}NOAA Webapp Console Simulation Test{RESET}")
        print(f"{BLUE}{'=' * 70}{RESET}")
        print(f"Target URL: {self.base_url}")

        # Test 1: HTML Load
        if not self.test_html_load():
            print(f"\n{RED}Critical failure: Cannot load HTML. Stopping tests.{RESET}")
            return False

        # Test 2: JavaScript Load
        js_loaded, js_content = self.test_javascript_load()
        if not js_loaded:
            print(
                f"\n{RED}Critical failure: Cannot load JavaScript. Stopping tests.{RESET}"
            )
            return False

        # Test 3: XML Tags
        self.test_xml_tags(js_content)

        # Test 4: Syntax Patterns
        self.test_syntax_patterns(js_content)

        # Test 5: Required Structures
        self.test_required_structures(js_content)

        # Test 6: Fallback Data
        self.test_fallback_data(js_content)

        # Test 7: API Endpoint
        self.test_api_endpoint()

        # Test 8: CloudFront Cache
        self.test_cloudfront_cache()

        # Generate report
        report = self.generate_report()

        return report["success"]


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test NOAA webapp for console errors")
    parser.add_argument(
        "--url",
        default="https://dq8oz5pgpnqc1.cloudfront.net",
        help="Base URL to test (default: CloudFront production)",
    )
    parser.add_argument("--output", help="Save report to JSON file")

    args = parser.parse_args()

    tester = WebappTester(args.url)
    success = tester.run_all_tests()

    # Save report if requested
    if args.output:
        import json

        report = {
            "url": args.url,
            "passed": tester.passed,
            "errors": tester.errors,
            "warnings": tester.warnings,
            "success": success,
        }
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to: {args.output}")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

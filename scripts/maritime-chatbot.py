#!/usr/bin/env python3
"""
NOAA Maritime Navigation Chatbot
Interactive CLI for maritime route planning with conversation history

Features:
- Two-way conversational interface
- Full data display (no arbitrary limits)
- AI-driven query interpretation
- Follow-up question support
- Rich maritime information presentation
"""

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

# Parse command line arguments
parser = argparse.ArgumentParser(description="NOAA Maritime Navigation Chatbot")
parser.add_argument(
    "--region", default="us-east-1", help="AWS region (default: us-east-1)"
)
parser.add_argument(
    "--function-name",
    default="noaa-intelligent-orchestrator-dev",
    help="Lambda function name",
)
args = parser.parse_args()

# Configuration
REGION = args.region
LAMBDA_FUNCTION = args.function_name


# Colors for terminal output
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


# Initialize AWS client
try:
    lambda_client = boto3.client("lambda", region_name=REGION)
except Exception as e:
    print(f"{Colors.RED}Error: Could not initialize AWS Lambda client.{Colors.ENDC}")
    print(f"Make sure you have AWS credentials configured.")
    sys.exit(1)


class MaritimeChatbot:
    """Interactive maritime navigation chatbot"""

    def __init__(self):
        self.conversation_history = []
        self.session_start = datetime.now()
        self.query_count = 0

    def print_welcome(self):
        """Print welcome message"""
        print(f"\n{Colors.CYAN}{'=' * 80}{Colors.ENDC}")
        print(
            f"{Colors.BOLD}{Colors.BLUE}🌊 NOAA Maritime Navigation Chatbot ⛵{Colors.ENDC}"
        )
        print(f"{Colors.CYAN}{'=' * 80}{Colors.ENDC}")
        print(
            f"\n{Colors.GREEN}Welcome to the NOAA Maritime Navigation Intelligence System!{Colors.ENDC}"
        )
        print(f"\nI can help you with:")
        print(f"  • Maritime route planning and safety assessment")
        print(f"  • Current weather conditions and forecasts")
        print(f"  • Wave heights, wind speeds, and sea conditions")
        print(f"  • Active marine weather alerts and advisories")
        print(f"  • Tide predictions and ocean currents")
        print(f"  • Observation station locations and data")
        print(
            f"\n{Colors.YELLOW}Ask me anything about maritime navigation in natural language!{Colors.ENDC}"
        )
        print(f"{Colors.CYAN}{'─' * 80}{Colors.ENDC}\n")
        print(
            f"Commands: {Colors.BOLD}help{Colors.ENDC}, {Colors.BOLD}history{Colors.ENDC}, {Colors.BOLD}clear{Colors.ENDC}, {Colors.BOLD}exit{Colors.ENDC}\n"
        )

    def print_help(self):
        """Print help information"""
        print(f"\n{Colors.CYAN}{'─' * 80}{Colors.ENDC}")
        print(f"{Colors.BOLD}Example Queries:{Colors.ENDC}\n")
        print(f"  {Colors.GREEN}Route Planning:{Colors.ENDC}")
        print(f"    • Plan a safe maritime route from Boston to Portland Maine")
        print(
            f"    • What are the conditions for sailing from San Francisco to Los Angeles?"
        )
        print(f"    • Is it safe to navigate from Seattle to Vancouver today?")
        print(f"\n  {Colors.GREEN}Weather & Conditions:{Colors.ENDC}")
        print(f"    • What's the current weather along the California coast?")
        print(f"    • Show me wave heights off Cape Cod")
        print(f"    • What are the wind conditions in the Gulf of Mexico?")
        print(f"\n  {Colors.GREEN}Alerts & Safety:{Colors.ENDC}")
        print(f"    • Are there any active marine weather alerts for Florida?")
        print(f"    • Check for small craft advisories in Chesapeake Bay")
        print(f"    • What warnings are active in the Pacific Northwest?")
        print(f"\n  {Colors.GREEN}Stations & Data:{Colors.ENDC}")
        print(f"    • Find weather stations near Miami")
        print(f"    • What buoys are near 40°N 70°W?")
        print(f"    • Show me tide gauges in San Francisco Bay")
        print(f"\n  {Colors.GREEN}Follow-up Questions:{Colors.ENDC}")
        print(f"    • Tell me more about that alert")
        print(f"    • What about tomorrow's forecast?")
        print(f"    • Show me the detailed wave data")
        print(f"{Colors.CYAN}{'─' * 80}{Colors.ENDC}\n")

    def print_history(self):
        """Print conversation history"""
        if not self.conversation_history:
            print(f"\n{Colors.YELLOW}No conversation history yet.{Colors.ENDC}\n")
            return

        print(f"\n{Colors.CYAN}{'─' * 80}{Colors.ENDC}")
        print(f"{Colors.BOLD}Conversation History:{Colors.ENDC}\n")

        for i, entry in enumerate(self.conversation_history, 1):
            timestamp = entry["timestamp"].strftime("%H:%M:%S")
            query = entry["query"]
            ponds = entry.get("ponds_queried", 0)
            records = entry.get("total_records", 0)

            print(
                f"{Colors.GREEN}[{timestamp}] Query {i}:{Colors.ENDC} {query[:60]}..."
            )
            print(
                f"  {Colors.CYAN}→ Queried {ponds} ponds, analyzed {records} records{Colors.ENDC}"
            )

        print(f"{Colors.CYAN}{'─' * 80}{Colors.ENDC}\n")

    def query_lambda(
        self, user_query: str, include_history: bool = True
    ) -> Dict[str, Any]:
        """Query the Lambda function with optional conversation history"""

        # Build payload with conversation context
        payload = {
            "query": user_query,
            "conversation_history": self.conversation_history[-3:]
            if include_history
            else [],
        }

        try:
            print(f"{Colors.YELLOW}🔍 Analyzing your query...{Colors.ENDC}")
            start_time = time.time()

            response = lambda_client.invoke(
                FunctionName=LAMBDA_FUNCTION,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload),
            )

            duration = time.time() - start_time

            # Parse response
            result = json.loads(response["Payload"].read())

            # Handle API Gateway format (body wrapped in JSON)
            if "body" in result:
                if isinstance(result["body"], str):
                    result = json.loads(result["body"])
                else:
                    result = result["body"]

            result["query_duration"] = duration

            return result

        except ClientError as e:
            return {"success": False, "error": f"AWS Error: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

    def format_maritime_data(self, data: Dict[str, Any]) -> str:
        """Format maritime data for display"""
        if not data.get("success"):
            return f"{Colors.RED}❌ Error: {data.get('error', 'Unknown error')}{Colors.ENDC}"

        output = []

        # Query information
        output.append(f"\n{Colors.CYAN}{'═' * 80}{Colors.ENDC}")
        output.append(f"{Colors.BOLD}{Colors.BLUE}📊 Query Results{Colors.ENDC}")
        output.append(f"{Colors.CYAN}{'═' * 80}{Colors.ENDC}\n")

        # Metadata
        if "metadata" in data:
            meta = data["metadata"]
            output.append(f"{Colors.GREEN}Analysis Summary:{Colors.ENDC}")
            output.append(f"  • Ponds Queried: {meta.get('ponds_queried', 0)}")
            output.append(
                f"  • Total Records Analyzed: {meta.get('total_records', 0):,}"
            )
            output.append(
                f"  • Processing Time: {meta.get('execution_time_ms', 0):.0f}ms"
            )
            output.append("")

        # Ponds queried details
        if "ponds_queried" in data and data["ponds_queried"]:
            output.append(f"{Colors.GREEN}Data Sources:{Colors.ENDC}")
            for pond in data["ponds_queried"]:
                pond_name = pond.get("pond", "Unknown")
                records = pond.get("records_found", 0)
                relevance = pond.get("relevance_score", 0) * 100
                contribution = pond.get("data_contribution", "")

                icon = "✓" if pond.get("success") else "✗"
                color = Colors.GREEN if pond.get("success") else Colors.RED

                output.append(f"  {color}{icon} {pond_name}{Colors.ENDC}")
                output.append(f"    ├─ Records: {records:,}")
                output.append(f"    ├─ Relevance: {relevance:.0f}%")
                if contribution:
                    output.append(f"    └─ Data: {contribution}")
            output.append("")

        # Main answer
        if "answer" in data:
            output.append(f"{Colors.CYAN}{'─' * 80}{Colors.ENDC}")
            output.append(
                f"{Colors.BOLD}{Colors.BLUE}📋 Maritime Analysis:{Colors.ENDC}\n"
            )

            # Process and format the answer
            answer = data["answer"]

            # Add colors to headers and important info
            answer = answer.replace("# ", f"\n{Colors.BOLD}{Colors.BLUE}")
            answer = answer.replace("## ", f"\n{Colors.BOLD}{Colors.GREEN}")
            answer = answer.replace("⚠️", f"{Colors.YELLOW}⚠️{Colors.ENDC}")
            answer = answer.replace("✅", f"{Colors.GREEN}✅{Colors.ENDC}")
            answer = answer.replace("❌", f"{Colors.RED}❌{Colors.ENDC}")

            output.append(answer)
            output.append(f"{Colors.ENDC}")

        # Raw data preview (if available and user wants it)
        if "raw_data" in data and data["raw_data"]:
            output.append(f"\n{Colors.CYAN}{'─' * 80}{Colors.ENDC}")
            output.append(
                f"{Colors.YELLOW}💾 Raw Data Available - Type 'show raw data' for details{Colors.ENDC}"
            )

        output.append(f"\n{Colors.CYAN}{'═' * 80}{Colors.ENDC}\n")

        return "\n".join(output)

    def handle_command(self, command: str) -> bool:
        """Handle special commands. Returns True if command was handled."""
        command = command.lower().strip()

        if command == "help":
            self.print_help()
            return True
        elif command == "history":
            self.print_history()
            return True
        elif command == "clear":
            self.conversation_history = []
            print(f"\n{Colors.GREEN}✓ Conversation history cleared.{Colors.ENDC}\n")
            return True
        elif command in ["exit", "quit", "bye"]:
            print(f"\n{Colors.CYAN}{'─' * 80}{Colors.ENDC}")
            print(
                f"{Colors.BLUE}Thanks for using NOAA Maritime Navigation Chatbot!{Colors.ENDC}"
            )
            print(f"\nSession Summary:")
            print(
                f"  • Duration: {(datetime.now() - self.session_start).total_seconds():.0f} seconds"
            )
            print(f"  • Queries: {self.query_count}")
            print(f"\n{Colors.GREEN}⛵ Safe sailing! 🌊{Colors.ENDC}")
            print(f"{Colors.CYAN}{'─' * 80}{Colors.ENDC}\n")
            return True

        return False

    def chat_loop(self):
        """Main chat loop"""
        self.print_welcome()

        try:
            while True:
                # Get user input
                try:
                    user_input = input(
                        f"{Colors.BOLD}{Colors.BLUE}You: {Colors.ENDC}"
                    ).strip()
                except EOFError:
                    break

                if not user_input:
                    continue

                # Check for commands
                if self.handle_command(user_input):
                    if user_input.lower() in ["exit", "quit", "bye"]:
                        break
                    continue

                # Query the system
                self.query_count += 1
                result = self.query_lambda(user_input)

                # Store in history
                history_entry = {
                    "timestamp": datetime.now(),
                    "query": user_input,
                    "ponds_queried": result.get("metadata", {}).get("ponds_queried", 0),
                    "total_records": result.get("metadata", {}).get("total_records", 0),
                    "response_summary": result.get("answer", "")[:200],
                }
                self.conversation_history.append(history_entry)

                # Display results
                formatted_output = self.format_maritime_data(result)
                print(formatted_output)

                # Suggest follow-up
                print(
                    f"{Colors.YELLOW}💬 You can ask follow-up questions or type 'help' for more options{Colors.ENDC}\n"
                )

        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}Interrupted by user.{Colors.ENDC}")
            self.handle_command("exit")
        except Exception as e:
            print(f"\n{Colors.RED}Fatal error: {str(e)}{Colors.ENDC}")
            sys.exit(1)


def main():
    """Main entry point"""
    chatbot = MaritimeChatbot()
    chatbot.chat_loop()


if __name__ == "__main__":
    main()

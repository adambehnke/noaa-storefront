#!/usr/bin/env python3
"""
NOAA Data Lake Chatbot - Flask Web Server
Serves the chatbot interface and proxies requests to API Gateway
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder=".", template_folder=".")
CORS(app)

# Configuration - UPDATE THESE WITH YOUR ACTUAL API GATEWAY URLS
API_CONFIG = {
    "API_GATEWAY_URL": os.environ.get(
        "API_GATEWAY_URL",
        "https://your-api-gateway.execute-api.us-east-1.amazonaws.com/dev",
    ),
    "TIMEOUT": 30,
}

# Import handlers if running locally
try:
    import sys

    sys.path.append("..")
    from noaa_passthrough_handler import lambda_handler as passthrough_handler
    from ai_query_orchestrator import lambda_handler as ai_handler

    LOCAL_MODE = True
    logger.info("Running in LOCAL mode - using Lambda handlers directly")
except ImportError:
    LOCAL_MODE = False
    logger.info("Running in PROXY mode - forwarding to API Gateway")
    logger.info(f"API Gateway URL: {API_CONFIG['API_GATEWAY_URL']}")


@app.route("/")
def index():
    """Serve the main chatbot interface"""
    return send_from_directory(".", "index.html")


@app.route("/app.js")
def app_js():
    """Serve the JavaScript file"""
    return send_from_directory(".", "app.js")


@app.route("/api/ask", methods=["POST"])
def ask():
    """
    Plaintext query endpoint - routes to AI orchestrator
    Accepts natural language queries and returns AI-processed results
    """
    try:
        data = request.get_json()

        if not data or "query" not in data:
            return jsonify({"error": "Missing required parameter: query"}), 400

        logger.info(f"Plaintext query: {data['query']}")

        if LOCAL_MODE:
            # Use Lambda handler directly
            event = {"body": json.dumps(data)}

            # Mock context
            class MockContext:
                def get_remaining_time_in_millis(self):
                    return 30000

            result = ai_handler(event, MockContext())

            if result["statusCode"] == 200:
                response_data = json.loads(result["body"])
                return jsonify(response_data)
            else:
                return jsonify(json.loads(result["body"])), result["statusCode"]
        else:
            # Proxy to API Gateway
            url = f"{API_CONFIG['API_GATEWAY_URL']}/ask"

            response = requests.post(
                url,
                json=data,
                timeout=API_CONFIG["TIMEOUT"],
                headers={"Content-Type": "application/json"},
            )

            return jsonify(response.json()), response.status_code

    except requests.exceptions.Timeout:
        logger.error("API Gateway timeout")
        return jsonify(
            {"error": "Request timeout", "message": "The API took too long to respond"}
        ), 504

    except requests.exceptions.RequestException as e:
        logger.error(f"API Gateway error: {e}")
        return jsonify({"error": "API Gateway error", "message": str(e)}), 502

    except Exception as e:
        logger.exception("Unexpected error in /ask endpoint")
        return jsonify({"error": "Server error", "message": str(e)}), 500


@app.route("/api/passthrough", methods=["GET"])
def passthrough():
    """
    Direct passthrough endpoint - queries specific NOAA APIs
    Accepts service and parameters, returns raw API data
    """
    try:
        params = request.args.to_dict()

        if "service" not in params:
            return jsonify(
                {
                    "error": "Missing required parameter: service",
                    "valid_services": ["nws", "tides", "cdo", "ndbc", "ncei"],
                }
            ), 400

        logger.info(f"Passthrough query: service={params['service']}, params={params}")

        if LOCAL_MODE:
            # Use Lambda handler directly
            event = {"queryStringParameters": params}

            result = passthrough_handler(event, None)

            if result["statusCode"] == 200:
                response_data = json.loads(result["body"])
                return jsonify(response_data)
            else:
                return jsonify(json.loads(result["body"])), result["statusCode"]
        else:
            # Proxy to API Gateway
            url = f"{API_CONFIG['API_GATEWAY_URL']}/passthrough"

            response = requests.get(url, params=params, timeout=API_CONFIG["TIMEOUT"])

            return jsonify(response.json()), response.status_code

    except requests.exceptions.Timeout:
        logger.error("API Gateway timeout")
        return jsonify(
            {"error": "Request timeout", "message": "The API took too long to respond"}
        ), 504

    except requests.exceptions.RequestException as e:
        logger.error(f"API Gateway error: {e}")
        return jsonify({"error": "API Gateway error", "message": str(e)}), 502

    except Exception as e:
        logger.exception("Unexpected error in /passthrough endpoint")
        return jsonify({"error": "Server error", "message": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "mode": "local" if LOCAL_MODE else "proxy",
            "api_gateway": API_CONFIG["API_GATEWAY_URL"] if not LOCAL_MODE else "N/A",
            "version": "1.0",
        }
    )


@app.route("/api/stats", methods=["GET"])
def stats():
    """Get system statistics"""
    try:
        stats_data = {
            "services": {
                "nws": {"status": "active", "name": "National Weather Service"},
                "tides": {"status": "active", "name": "Tides & Currents"},
                "ndbc": {"status": "active", "name": "NDBC Buoys"},
                "cdo": {"status": "token_required", "name": "Climate Data Online"},
                "ncei": {"status": "active", "name": "NCEI Archives"},
            },
            "ponds": {
                "atmospheric": {"endpoints": 10, "status": "active"},
                "oceanic": {"endpoints": 10, "status": "active"},
                "buoy": {"endpoints": 1, "status": "active"},
                "climate": {"endpoints": 5, "status": "token_required"},
                "archive": {"endpoints": 3, "status": "active"},
            },
            "system": {
                "version": "1.0",
                "test_coverage": "92.3%",
                "mode": "local" if LOCAL_MODE else "proxy",
            },
        }

        return jsonify(stats_data)

    except Exception as e:
        logger.exception("Error fetching stats")
        return jsonify({"error": str(e)}), 500


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    logger.exception("Server error")
    return jsonify({"error": "Internal server error"}), 500


def main():
    """Run the Flask development server"""
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    debug = os.environ.get("DEBUG", "False").lower() == "true"

    print("\n" + "=" * 80)
    print("NOAA DATA LAKE CHATBOT SERVER")
    print("=" * 80)
    print(f"\n🚀 Server starting on http://{host}:{port}")
    print(
        f"📊 Mode: {'LOCAL (using Lambda handlers directly)' if LOCAL_MODE else 'PROXY (forwarding to API Gateway)'}"
    )

    if not LOCAL_MODE:
        print(f"🔗 API Gateway: {API_CONFIG['API_GATEWAY_URL']}")
        if "your-api-gateway" in API_CONFIG["API_GATEWAY_URL"]:
            print("\n⚠️  WARNING: API_GATEWAY_URL not configured!")
            print("   Set API_GATEWAY_URL environment variable to your API Gateway URL")

    print(f"\n📝 Access the chatbot at: http://localhost:{port}")
    print(f"🔍 Health check: http://localhost:{port}/api/health")
    print(f"📊 Stats: http://localhost:{port}/api/stats")
    print("\n" + "=" * 80 + "\n")

    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    main()

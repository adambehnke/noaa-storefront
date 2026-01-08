#!/usr/bin/env python3
"""
Add Image URL Fields to NOAA Data Lake
======================================

This script enhances the spatial pond data with direct image URLs for:
- Radar imagery (Ridge Radar)
- Satellite imagery (GOES-16/17/18)
- Weather maps and charts

Usage:
    python3 add_image_url_fields.py --env dev --update-lambda
    python3 add_image_url_fields.py --env dev --transform-data
    python3 add_image_url_fields.py --test-urls

Author: NOAA Data Lake Team
Date: January 2026
"""

import argparse
import json
import sys
from datetime import datetime
from typing import Dict, List, Optional

import boto3
import requests


class ImageURLEnhancer:
    """Enhance NOAA data with image URLs for maps and visualizations"""

    def __init__(self, env="dev"):
        self.env = env
        self.s3_client = boto3.client("s3")
        self.lambda_client = boto3.client("lambda")

    # Sector mapping based on geographic location
    SECTOR_MAP = {
        "northeast": "ne",
        "southeast": "se",
        "midwest": "mw",
        "southwest": "sw",
        "northwest": "nw",
        "conus": "conus",
        "alaska": "ak",
        "hawaii": "hi",
        "puerto_rico": "pr",
    }

    def get_sector_from_coordinates(self, lat: float, lon: float) -> str:
        """Determine GOES satellite sector based on coordinates"""
        # Continental US
        if 24 <= lat <= 50 and -125 <= lon <= -66:
            if lat >= 37 and lon >= -85:
                return "ne"  # Northeast
            elif lat < 37 and lon >= -85:
                return "se"  # Southeast
            elif lat >= 41 and lon < -95:
                return "nw"  # Northwest
            elif lat < 41 and lon < -95:
                return "sw"  # Southwest
            else:
                return "mw"  # Midwest
        # Alaska
        elif lat >= 51 or (lat >= 45 and lon < -130):
            return "ak"
        # Hawaii
        elif 18 <= lat <= 23 and -161 <= lon <= -154:
            return "hi"
        # Puerto Rico
        elif 17 <= lat <= 19 and -68 <= lon <= -65:
            return "pr"
        else:
            return "conus"  # Default to full CONUS view

    def generate_radar_urls(self, radar_station: str) -> Dict[str, str]:
        """Generate radar image URLs for a given station"""
        if not radar_station:
            return {}

        station = radar_station.upper()

        return {
            "radar_image_loop": f"https://radar.weather.gov/ridge/standard/{station}_loop.gif",
            "radar_image_static": f"https://radar.weather.gov/ridge/standard/{station}_0.gif",
            "radar_image_lite": f"https://radar.weather.gov/ridge/lite/{station}_loop.gif",
            "radar_wms_url": "https://opengeo.ncep.noaa.gov/geoserver/conus/conus_bref_qcd/ows",
            "radar_station_url": f"https://api.weather.gov/radar/stations/{station}",
            "radar_interactive": f"https://radar.weather.gov/station/{station.lower()}",
        }

    def generate_satellite_urls(
        self, lat: float, lon: float, sector: Optional[str] = None
    ) -> Dict[str, str]:
        """Generate satellite image URLs for a location"""
        if sector is None:
            sector = self.get_sector_from_coordinates(lat, lon)

        base_goes16 = "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/SECTOR"
        base_goes17 = "https://cdn.star.nesdis.noaa.gov/GOES17/ABI/SECTOR"

        urls = {
            "satellite_geocolor": f"{base_goes16}/{sector}/GEOCOLOR/latest.jpg",
            "satellite_visible": f"{base_goes16}/{sector}/02/latest.jpg",
            "satellite_infrared": f"{base_goes16}/{sector}/13/latest.jpg",
            "satellite_water_vapor": f"{base_goes16}/{sector}/08/latest.jpg",
            "satellite_sector": sector,
            "satellite_interactive": f"https://www.star.nesdis.noaa.gov/GOES/sector.php?sat=G16&sector={sector}",
        }

        # For western US, add GOES-17 as well
        if lon < -100:
            urls["satellite_geocolor_west"] = (
                f"{base_goes17}/{sector}/GEOCOLOR/latest.jpg"
            )

        return urls

    def generate_weather_map_urls(self, state: Optional[str] = None) -> Dict[str, str]:
        """Generate weather map and chart URLs"""
        urls = {
            "surface_analysis": "https://www.wpc.ncep.noaa.gov/noaa/noaa.gif",
            "surface_analysis_color": "https://www.wpc.ncep.noaa.gov/noaa/noaad1.gif",
            "forecast_chart_day1": "https://www.wpc.ncep.noaa.gov/basicwx/basicwx_ndfd.php",
            "marine_forecast": "https://www.wpc.ncep.noaa.gov/sfc/namussfc.gif",
            "precipitation_analysis": "https://www.wpc.ncep.noaa.gov/qpf/p24i.gif",
            "weather_prediction": "https://www.wpc.ncep.noaa.gov/metwatch/metwatch_ndfd.php",
        }

        return urls

    def generate_marine_chart_urls(self, lat: float, lon: float) -> Dict[str, str]:
        """Generate marine chart URLs for coastal locations"""
        return {
            "nautical_charts": "https://www.nauticalcharts.noaa.gov/",
            "marine_charts_viewer": "https://charts.noaa.gov/",
            "coastal_data_viewer": "https://coast.noaa.gov/dataviewer/",
            "marine_forecast_map": "https://www.wpc.ncep.noaa.gov/sfc/namussfc.gif",
        }

    def enhance_spatial_record(self, record: Dict) -> Dict:
        """Add image URL fields to a spatial pond record"""
        enhanced = record.copy()

        # Extract existing data
        radar_station = record.get("radar_station", "")
        lat = record.get("latitude", 0)
        lon = record.get("longitude", 0)
        state = record.get("state", "")

        # Add radar URLs
        if radar_station:
            enhanced.update(self.generate_radar_urls(radar_station))

        # Add satellite URLs
        if lat and lon:
            enhanced.update(self.generate_satellite_urls(lat, lon))

        # Add weather map URLs
        enhanced.update(self.generate_weather_map_urls(state))

        # Add marine chart URLs if coastal
        if lat and lon and self.is_coastal(lat, lon):
            enhanced.update(self.generate_marine_chart_urls(lat, lon))

        # Add metadata
        enhanced["image_urls_added"] = datetime.utcnow().isoformat()
        enhanced["image_urls_version"] = "1.0"

        return enhanced

    def is_coastal(self, lat: float, lon: float) -> bool:
        """Check if location is coastal (simplified)"""
        # Coastal states roughly
        coastal_bounds = [
            (24, 50, -124, -117),  # West Coast
            (25, 31, -97, -80),  # Gulf Coast
            (25, 45, -80, -66),  # East Coast
        ]

        for min_lat, max_lat, min_lon, max_lon in coastal_bounds:
            if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                return True
        return False

    def test_image_urls(
        self, radar_station: str = "KBOX", lat: float = 42.3601, lon: float = -71.0589
    ):
        """Test generated image URLs to verify they work"""
        print("=" * 80)
        print("TESTING IMAGE URL GENERATION")
        print("=" * 80)
        print(f"\nTest Location: lat={lat}, lon={lon}, radar={radar_station}\n")

        # Generate all URLs
        radar_urls = self.generate_radar_urls(radar_station)
        satellite_urls = self.generate_satellite_urls(lat, lon)
        weather_urls = self.generate_weather_map_urls()

        all_urls = {**radar_urls, **satellite_urls, **weather_urls}

        # Test each URL
        print("Testing URL accessibility:\n")
        results = []

        for name, url in all_urls.items():
            try:
                response = requests.head(url, timeout=5, allow_redirects=True)
                status = (
                    "✅ OK"
                    if response.status_code == 200
                    else f"⚠️ {response.status_code}"
                )
                results.append((name, status, url))
                print(f"{status} - {name}")
                print(f"    {url}")
            except Exception as e:
                results.append((name, f"❌ ERROR", url))
                print(f"❌ ERROR - {name}")
                print(f"    {url}")
                print(f"    Error: {str(e)[:50]}")
            print()

        # Summary
        ok_count = sum(1 for r in results if "OK" in r[1])
        total = len(results)
        print("=" * 80)
        print(f"RESULTS: {ok_count}/{total} URLs accessible")
        print("=" * 80)

        return results

    def generate_lambda_code_snippet(self) -> str:
        """Generate code to add to Lambda function"""
        code = '''
# Add this to your spatial lambda_function.py in the ingest_location_metadata method

def enhance_with_image_urls(record, radar_station, lat, lon):
    """Add image URLs to spatial record"""

    # Radar URLs
    if radar_station:
        station = radar_station.upper()
        record['radar_image_loop'] = f'https://radar.weather.gov/ridge/standard/{station}_loop.gif'
        record['radar_image_static'] = f'https://radar.weather.gov/ridge/standard/{station}_0.gif'
        record['radar_wms_url'] = 'https://opengeo.ncep.noaa.gov/geoserver/conus/conus_bref_qcd/ows'

    # Satellite URLs (determine sector)
    sector = 'conus'
    if lat >= 37 and lon >= -85:
        sector = 'ne'
    elif lat < 37 and lon >= -85:
        sector = 'se'
    elif lat >= 41 and lon < -95:
        sector = 'nw'
    elif lat < 41 and lon < -95:
        sector = 'sw'
    else:
        sector = 'mw'

    record['satellite_geocolor'] = f'https://cdn.star.nesdis.noaa.gov/GOES16/ABI/SECTOR/{sector}/GEOCOLOR/latest.jpg'
    record['satellite_sector'] = sector

    # Weather map URLs
    record['surface_analysis'] = 'https://www.wpc.ncep.noaa.gov/noaa/noaa.gif'
    record['marine_forecast'] = 'https://www.wpc.ncep.noaa.gov/sfc/namussfc.gif'

    return record

# Then in your ingest_location_metadata method, add:
record = enhance_with_image_urls(record, radar_station, lat, lon)
'''
        return code

    def print_example_data(self):
        """Print example of enhanced data structure"""
        example = {
            "location_name": "Boston",
            "latitude": 42.3601,
            "longitude": -71.0589,
            "radar_station": "KBOX",
            # NEW: Radar Image URLs
            "radar_image_loop": "https://radar.weather.gov/ridge/standard/KBOX_loop.gif",
            "radar_image_static": "https://radar.weather.gov/ridge/standard/KBOX_0.gif",
            "radar_image_lite": "https://radar.weather.gov/ridge/lite/KBOX_loop.gif",
            "radar_wms_url": "https://opengeo.ncep.noaa.gov/geoserver/conus/conus_bref_qcd/ows",
            "radar_interactive": "https://radar.weather.gov/station/kbox",
            # NEW: Satellite Image URLs
            "satellite_geocolor": "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/SECTOR/ne/GEOCOLOR/latest.jpg",
            "satellite_visible": "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/SECTOR/ne/02/latest.jpg",
            "satellite_infrared": "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/SECTOR/ne/13/latest.jpg",
            "satellite_sector": "ne",
            # NEW: Weather Map URLs
            "surface_analysis": "https://www.wpc.ncep.noaa.gov/noaa/noaa.gif",
            "marine_forecast": "https://www.wpc.ncep.noaa.gov/sfc/namussfc.gif",
            # Existing fields
            "grid_id": "BOX",
            "grid_x": 71,
            "grid_y": 90,
            "forecast_url": "https://api.weather.gov/gridpoints/BOX/71,90/forecast",
        }

        print("\n" + "=" * 80)
        print("EXAMPLE ENHANCED DATA STRUCTURE")
        print("=" * 80)
        print(json.dumps(example, indent=2))
        print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Add image URL fields to NOAA Data Lake spatial pond",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test URL generation
  python3 add_image_url_fields.py --test-urls

  # Show example data structure
  python3 add_image_url_fields.py --show-example

  # Generate Lambda code
  python3 add_image_url_fields.py --generate-code

  # Test with custom location
  python3 add_image_url_fields.py --test-urls --radar KLAX --lat 34.0522 --lon -118.2437
        """,
    )

    parser.add_argument("--env", default="dev", help="Environment (dev/staging/prod)")
    parser.add_argument(
        "--test-urls", action="store_true", help="Test image URL accessibility"
    )
    parser.add_argument(
        "--show-example", action="store_true", help="Show example enhanced data"
    )
    parser.add_argument(
        "--generate-code", action="store_true", help="Generate Lambda code snippet"
    )
    parser.add_argument("--radar", default="KBOX", help="Radar station for testing")
    parser.add_argument(
        "--lat", type=float, default=42.3601, help="Latitude for testing"
    )
    parser.add_argument(
        "--lon", type=float, default=-71.0589, help="Longitude for testing"
    )

    args = parser.parse_args()

    enhancer = ImageURLEnhancer(args.env)

    if args.test_urls:
        enhancer.test_image_urls(args.radar, args.lat, args.lon)

    if args.show_example:
        enhancer.print_example_data()

    if args.generate_code:
        print("\n" + "=" * 80)
        print("LAMBDA FUNCTION CODE SNIPPET")
        print("=" * 80)
        print(enhancer.generate_lambda_code_snippet())
        print("=" * 80 + "\n")

    if not (args.test_urls or args.show_example or args.generate_code):
        print("No action specified. Use --help for options.")
        print("\nQuick start:")
        print("  python3 add_image_url_fields.py --test-urls")
        print("  python3 add_image_url_fields.py --show-example")
        print("  python3 add_image_url_fields.py --generate-code")


if __name__ == "__main__":
    main()

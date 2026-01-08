#!/usr/bin/env python3
"""
NOAA Federated Data Lake - Stream Producer Test Script

This script tests the real-time streaming infrastructure by sending
simulated NOAA data to Kinesis Data Streams.

Usage:
    python test_stream_producer.py --stream atmospheric --count 100
    python test_stream_producer.py --stream all --rate 10
    python test_stream_producer.py --stream oceanic --single

Requirements:
    pip install boto3 faker
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError

# Stream names by pond type
STREAM_NAMES = {
    "atmospheric": "noaa-stream-atmospheric-dev",
    "oceanic": "noaa-stream-oceanic-dev",
    "buoy": "noaa-stream-buoy-dev",
}

# Sample station IDs
ATMOSPHERIC_STATIONS = ["KBOS", "KJFK", "KSEA", "KLAX", "KORD", "KATL", "KDFW", "KDEN"]
OCEANIC_STATIONS = ["9414290", "8454000", "8518750", "8658120", "8729108", "9410170"]
BUOY_IDS = ["46035", "46011", "46029", "44013", "41001", "41002", "42001", "42003"]


class StreamDataGenerator:
    """Generate realistic NOAA data for testing"""

    @staticmethod
    def generate_atmospheric_data() -> Dict[str, Any]:
        """Generate atmospheric observation data"""
        station_id = random.choice(ATMOSPHERIC_STATIONS)
        base_temp = 60 + random.uniform(-20, 40)  # 40-100°F range

        return {
            "station_id": station_id,
            "observation_time": datetime.utcnow().isoformat() + "Z",
            "temperature": round(base_temp, 1),
            "feels_like": round(base_temp + random.uniform(-5, 5), 1),
            "pressure": round(random.uniform(980, 1040), 2),
            "humidity": round(random.uniform(20, 95), 1),
            "wind_speed": round(random.uniform(0, 35), 1),
            "wind_direction": random.randint(0, 359),
            "wind_gust": round(random.uniform(0, 45), 1),
            "visibility": round(random.uniform(0.5, 10), 1),
            "cloud_coverage": random.choice(
                ["clear", "partly_cloudy", "cloudy", "overcast"]
            ),
            "weather_condition": random.choice(
                ["clear", "rain", "snow", "fog", "thunderstorm"]
            ),
            "dewpoint": round(base_temp - random.uniform(5, 20), 1),
            "latitude": round(random.uniform(25, 48), 6),
            "longitude": round(random.uniform(-125, -70), 6),
            "elevation": random.randint(0, 5000),
            "data_quality": random.choice(["good", "good", "good", "fair", "poor"]),
            "ingestion_timestamp": datetime.utcnow().isoformat() + "Z",
        }

    @staticmethod
    def generate_oceanic_data() -> Dict[str, Any]:
        """Generate oceanic/tides observation data"""
        station_id = random.choice(OCEANIC_STATIONS)

        return {
            "station_id": station_id,
            "observation_time": datetime.utcnow().isoformat() + "Z",
            "water_level": round(random.uniform(-2.0, 8.0), 3),
            "water_temperature": round(random.uniform(40, 85), 2),
            "salinity": round(random.uniform(30, 37), 2),
            "conductivity": round(random.uniform(40, 60), 2),
            "dissolved_oxygen": round(random.uniform(5, 12), 2),
            "ph_level": round(random.uniform(7.5, 8.5), 2),
            "turbidity": round(random.uniform(0, 50), 2),
            "wave_height": round(random.uniform(0, 6), 2),
            "wave_period": round(random.uniform(3, 15), 1),
            "current_speed": round(random.uniform(0, 3), 2),
            "current_direction": random.randint(0, 359),
            "tide_stage": random.choice(["rising", "falling", "high", "low"]),
            "latitude": round(random.uniform(25, 48), 6),
            "longitude": round(random.uniform(-125, -70), 6),
            "data_quality": random.choice(["good", "good", "good", "fair"]),
            "ingestion_timestamp": datetime.utcnow().isoformat() + "Z",
        }

    @staticmethod
    def generate_buoy_data() -> Dict[str, Any]:
        """Generate buoy telemetry data"""
        buoy_id = random.choice(BUOY_IDS)

        return {
            "buoy_id": buoy_id,
            "observation_time": datetime.utcnow().isoformat() + "Z",
            "latitude": round(random.uniform(25, 48), 6),
            "longitude": round(random.uniform(-125, -70), 6),
            "wind_speed": round(random.uniform(0, 40), 1),
            "wind_direction": random.randint(0, 359),
            "wind_gust": round(random.uniform(0, 50), 1),
            "wave_height": round(random.uniform(0, 10), 2),
            "dominant_wave_period": round(random.uniform(3, 20), 1),
            "average_wave_period": round(random.uniform(2, 15), 1),
            "wave_direction": random.randint(0, 359),
            "sea_level_pressure": round(random.uniform(980, 1040), 2),
            "air_temperature": round(random.uniform(40, 95), 1),
            "water_temperature": round(random.uniform(40, 85), 1),
            "dewpoint_temperature": round(random.uniform(35, 80), 1),
            "visibility": round(random.uniform(0, 20), 1),
            "tide_height": round(random.uniform(-1, 3), 2),
            "buoy_status": random.choice(["active", "active", "active", "warning"]),
            "battery_voltage": round(random.uniform(11.5, 14.5), 2),
            "data_quality": random.choice(["good", "good", "good", "fair"]),
            "ingestion_timestamp": datetime.utcnow().isoformat() + "Z",
        }


class StreamProducer:
    """Kinesis stream producer for testing"""

    def __init__(self, region: str = "us-east-1", profile: str = None):
        """Initialize stream producer"""
        session_kwargs = {"region_name": region}
        if profile:
            session_kwargs["profile_name"] = profile

        session = boto3.Session(**session_kwargs)
        self.kinesis = session.client("kinesis")
        self.cloudwatch = session.client("cloudwatch")
        self.generator = StreamDataGenerator()
        self.stats = {
            "sent": 0,
            "failed": 0,
            "bytes_sent": 0,
            "start_time": time.time(),
        }

    def send_record(
        self, stream_name: str, data: Dict[str, Any], partition_key: str
    ) -> bool:
        """Send a single record to Kinesis stream"""
        try:
            data_json = json.dumps(data)
            response = self.kinesis.put_record(
                StreamName=stream_name, Data=data_json, PartitionKey=partition_key
            )

            self.stats["sent"] += 1
            self.stats["bytes_sent"] += len(data_json)

            print(f"✓ Sent record to {stream_name}")
            print(f"  Sequence Number: {response['SequenceNumber']}")
            print(f"  Shard ID: {response['ShardId']}")
            print(f"  Data: {data_json[:100]}...")

            return True

        except ClientError as e:
            self.stats["failed"] += 1
            print(f"✗ Failed to send record: {e}")
            return False

    def send_batch(self, stream_name: str, records: List[Dict[str, Any]]) -> int:
        """Send batch of records to Kinesis stream"""
        try:
            kinesis_records = [
                {
                    "Data": json.dumps(record),
                    "PartitionKey": record.get("station_id")
                    or record.get("buoy_id", "default"),
                }
                for record in records
            ]

            response = self.kinesis.put_records(
                StreamName=stream_name, Records=kinesis_records
            )

            failed_count = response["FailedRecordCount"]
            success_count = len(records) - failed_count

            self.stats["sent"] += success_count
            self.stats["failed"] += failed_count
            self.stats["bytes_sent"] += sum(len(json.dumps(r)) for r in records)

            print(
                f"✓ Batch sent to {stream_name}: {success_count} succeeded, {failed_count} failed"
            )

            return success_count

        except ClientError as e:
            self.stats["failed"] += len(records)
            print(f"✗ Failed to send batch: {e}")
            return 0

    def generate_and_send(
        self,
        pond_type: str,
        stream_name: str,
        count: int,
        rate: float = None,
        batch_size: int = 100,
    ):
        """Generate and send test data"""
        print(f"\n{'=' * 60}")
        print(f"Sending {count} records to {pond_type} stream")
        print(f"Stream: {stream_name}")
        if rate:
            print(f"Rate: {rate} records/second")
        print(f"{'=' * 60}\n")

        # Generate data based on pond type
        generator_map = {
            "atmospheric": self.generator.generate_atmospheric_data,
            "oceanic": self.generator.generate_oceanic_data,
            "buoy": self.generator.generate_buoy_data,
        }

        generate_func = generator_map.get(pond_type)
        if not generate_func:
            print(f"✗ Unknown pond type: {pond_type}")
            return

        records = []
        for i in range(count):
            data = generate_func()
            records.append(data)

            # Send in batches or respect rate limit
            if len(records) >= batch_size or i == count - 1:
                self.send_batch(stream_name, records)
                records = []

                # Rate limiting
                if rate:
                    time.sleep(batch_size / rate)

            # Progress indicator
            if (i + 1) % 100 == 0:
                print(f"Progress: {i + 1}/{count} records sent")

    def send_continuous(
        self, pond_type: str, stream_name: str, rate: float, duration: int
    ):
        """Send continuous stream of data"""
        print(f"\n{'=' * 60}")
        print(f"Continuous streaming to {pond_type}")
        print(f"Rate: {rate} records/second")
        print(f"Duration: {duration} seconds")
        print(f"Press Ctrl+C to stop")
        print(f"{'=' * 60}\n")

        generator_map = {
            "atmospheric": self.generator.generate_atmospheric_data,
            "oceanic": self.generator.generate_oceanic_data,
            "buoy": self.generator.generate_buoy_data,
        }

        generate_func = generator_map[pond_type]
        end_time = time.time() + duration

        try:
            while time.time() < end_time:
                data = generate_func()
                partition_key = data.get("station_id") or data.get("buoy_id", "default")
                self.send_record(stream_name, data, partition_key)

                time.sleep(1.0 / rate)

        except KeyboardInterrupt:
            print("\n\nStopping continuous stream...")

    def print_statistics(self):
        """Print sending statistics"""
        duration = time.time() - self.stats["start_time"]
        rate = self.stats["sent"] / duration if duration > 0 else 0

        print(f"\n{'=' * 60}")
        print("STATISTICS")
        print(f"{'=' * 60}")
        print(f"Total Records Sent:     {self.stats['sent']}")
        print(f"Failed Records:         {self.stats['failed']}")
        print(
            f"Success Rate:           {(self.stats['sent'] / (self.stats['sent'] + self.stats['failed']) * 100) if self.stats['sent'] + self.stats['failed'] > 0 else 0:.2f}%"
        )
        print(
            f"Total Bytes Sent:       {self.stats['bytes_sent']:,} bytes ({self.stats['bytes_sent'] / 1024 / 1024:.2f} MB)"
        )
        print(f"Duration:               {duration:.2f} seconds")
        print(f"Average Rate:           {rate:.2f} records/second")
        print(f"{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Test NOAA real-time streaming infrastructure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Send 100 atmospheric records
  python test_stream_producer.py --stream atmospheric --count 100

  # Send data to all streams
  python test_stream_producer.py --stream all --count 50

  # Send at specific rate (records per second)
  python test_stream_producer.py --stream oceanic --count 1000 --rate 10

  # Continuous streaming
  python test_stream_producer.py --stream buoy --continuous --rate 5 --duration 300

  # Single test record
  python test_stream_producer.py --stream atmospheric --single
        """,
    )

    parser.add_argument(
        "--stream",
        choices=["atmospheric", "oceanic", "buoy", "all"],
        default="atmospheric",
        help="Stream to send data to",
    )
    parser.add_argument(
        "--count", type=int, default=10, help="Number of records to send (default: 10)"
    )
    parser.add_argument(
        "--rate", type=float, help="Records per second (for rate limiting)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for put_records (default: 100, max: 500)",
    )
    parser.add_argument(
        "--profile",
        default="noaa-target",
        help="AWS profile to use (default: noaa-target)",
    )
    parser.add_argument(
        "--region", default="us-east-1", help="AWS region (default: us-east-1)"
    )
    parser.add_argument(
        "--single", action="store_true", help="Send a single test record"
    )
    parser.add_argument(
        "--continuous", action="store_true", help="Send continuous stream of data"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration for continuous mode in seconds (default: 60)",
    )

    args = parser.parse_args()

    # Validate batch size
    if args.batch_size > 500:
        print("✗ Batch size cannot exceed 500 (Kinesis limit)")
        sys.exit(1)

    # Initialize producer
    producer = StreamProducer(region=args.region, profile=args.profile)

    try:
        if args.single:
            # Send single test record
            stream_name = STREAM_NAMES[args.stream]
            data = getattr(producer.generator, f"generate_{args.stream}_data")()
            partition_key = data.get("station_id") or data.get("buoy_id", "test")
            producer.send_record(stream_name, data, partition_key)

        elif args.continuous:
            # Continuous streaming mode
            if args.stream == "all":
                print("✗ Continuous mode not supported for 'all' streams")
                sys.exit(1)

            stream_name = STREAM_NAMES[args.stream]
            rate = args.rate or 1.0
            producer.send_continuous(args.stream, stream_name, rate, args.duration)

        elif args.stream == "all":
            # Send to all streams
            for pond_type, stream_name in STREAM_NAMES.items():
                producer.generate_and_send(
                    pond_type, stream_name, args.count, args.rate, args.batch_size
                )

        else:
            # Send to specific stream
            stream_name = STREAM_NAMES[args.stream]
            producer.generate_and_send(
                args.stream, stream_name, args.count, args.rate, args.batch_size
            )

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)

    finally:
        # Print statistics
        producer.print_statistics()


if __name__ == "__main__":
    main()

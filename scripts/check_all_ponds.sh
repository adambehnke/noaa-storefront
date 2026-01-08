#!/bin/bash
source config/environment.sh
echo "Checking all ponds for recent data..."
echo ""

for pond in atmospheric oceanic buoy climate terrestrial spatial; do
    echo "================================"
    echo "POND: $(echo $pond | tr '[:lower:]' '[:upper:]')"
    echo "================================"
    
    echo "Bronze Layer:"
    bronze_count=$(aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/${pond}/ --recursive 2>/dev/null | wc -l)
    echo "  Files: $bronze_count"
    latest_bronze=$(aws s3 ls s3://noaa-federated-lake-899626030376-dev/bronze/${pond}/ --recursive 2>/dev/null | tail -1 | awk '{print $1, $2}')
    echo "  Latest: $latest_bronze"
    
    echo "Gold Layer:"
    gold_count=$(aws s3 ls s3://noaa-federated-lake-899626030376-dev/gold/${pond}/ --recursive 2>/dev/null | wc -l)
    echo "  Files: $gold_count"
    latest_gold=$(aws s3 ls s3://noaa-federated-lake-899626030376-dev/gold/${pond}/ --recursive 2>/dev/null | tail -1 | awk '{print $1, $2}')
    echo "  Latest: $latest_gold"
    
    echo ""
done

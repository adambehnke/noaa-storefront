#!/usr/bin/env python3
"""Generate fresh pond metadata from S3"""
import boto3
import json
from datetime import datetime
from collections import defaultdict

s3 = boto3.client('s3', region_name='us-east-1')
bucket = 'noaa-federated-lake-899626030376-dev'

ponds = ['atmospheric', 'oceanic', 'buoy', 'climate', 'spatial', 'terrestrial']
result = {'collection_timestamp': datetime.utcnow().isoformat(), 'ponds': {}}

for pond in ponds:
    print(f"Processing {pond}...")
    pond_data = {'layers': {}}
    
    for layer in ['bronze', 'silver', 'gold']:
        prefix = f'{layer}/{pond}/'
        paginator = s3.get_paginator('list_objects_v2')
        
        files = []
        total_size = 0
        latest_time = None
        oldest_time = None
        
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            if 'Contents' not in page:
                continue
            
            for obj in page['Contents']:
                files.append(obj)
                total_size += obj.get('Size', 0)
                
                mod_time = obj['LastModified']
                if latest_time is None or mod_time > latest_time:
                    latest_time = mod_time
                if oldest_time is None or mod_time < oldest_time:
                    oldest_time = mod_time
        
        pond_data['layers'][layer] = {
            'file_count': len(files),
            'size_bytes': total_size,
            'size_mb': round(total_size / 1024 / 1024, 2),
            'latest_file': latest_time.isoformat() if latest_time else None,
            'oldest_file': oldest_time.isoformat() if oldest_time else None
        }
    
    # Calculate totals
    total_files = sum(l['file_count'] for l in pond_data['layers'].values())
    total_size = sum(l['size_bytes'] for l in pond_data['layers'].values())
    
    pond_data['total_files'] = total_files
    pond_data['total_size_mb'] = round(total_size / 1024 / 1024, 2)
    pond_data['total_size_gb'] = round(total_size / 1024 / 1024 / 1024, 2)
    
    # Get latest across all layers
    latest_times = [l['latest_file'] for l in pond_data['layers'].values() if l['latest_file']]
    if latest_times:
        pond_data['latest_ingestion'] = max(latest_times)
    
    result['ponds'][pond] = pond_data
    print(f"  ✓ {total_files:,} files, {pond_data['total_size_gb']} GB")

print("\nWriting pond_metadata.json...")
with open('../webapp/pond_metadata.json', 'w') as f:
    json.dump(result, f, indent=2)

print("✓ Done!")

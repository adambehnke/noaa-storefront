import json
import boto3
from datetime import datetime

s3 = boto3.client('s3')
BUCKET = 'noaa-federated-lake-899626030376-dev'

def lambda_handler(event, context):
    params = event.get('queryStringParameters', {}) or {}
    pond = params.get('pond_name', '')
    
    if not pond:
        return {'statusCode': 400, 'body': json.dumps({'error': 'pond_name required'})}
    
    # List files from bronze layer with pagination
    recent_data = []
    all_files = []
    prefix = f'bronze/{pond}/'
    
    paginator = s3.get_paginator('list_objects_v2')
    page_iterator = paginator.paginate(
        Bucket=BUCKET,
        Prefix=prefix,
        PaginationConfig={'MaxItems': 1000}
    )
    
    for page in page_iterator:
        if 'Contents' in page:
            all_files.extend(page['Contents'])
    
    # Sort by LastModified descending, get 5 most recent
    sorted_files = sorted(all_files, key=lambda x: x['LastModified'], reverse=True)[:5]
    
    for file in sorted_files:
        if file['Key'].endswith('.json') and file['Size'] < 200000:
            try:
                obj = s3.get_object(Bucket=BUCKET, Key=file['Key'])
                content = json.loads(obj['Body'].read())
                
                if isinstance(content, list):
                    content = content[0] if content else {}
                
                recent_data.append({
                    'key': file['Key'],
                    'size': file['Size'],
                    'last_modified': file['LastModified'].isoformat(),
                    'data': content
                })
            except Exception as e:
                print(f"Error: {e}")
    
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({
            'pond_name': pond,
            'recent_data': recent_data,
            'timestamp': datetime.utcnow().isoformat()
        })
    }

import json
import boto3
from datetime import datetime, timedelta

s3 = boto3.client('s3')
BUCKET = 'noaa-federated-lake-899626030376-dev'

def lambda_handler(event, context):
    params = event.get('queryStringParameters', {}) or {}
    pond = params.get('pond_name', '')
    
    if not pond:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'pond_name required'})
        }
    
    # Get recent files from bronze layer
    recent_data = []
    prefix = f'bronze/{pond}/'
    
    # List recent files (limit to 100 for speed)
    response = s3.list_objects_v2(
        Bucket=BUCKET,
        Prefix=prefix,
        MaxKeys=100
    )
    
    if 'Contents' in response:
        # Sort by last modified, get 5 most recent
        files = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)[:5]
        
        for file in files:
            if file['Key'].endswith('.json') and file['Size'] < 100000:  # Only small JSON files
                try:
                    obj = s3.get_object(Bucket=BUCKET, Key=file['Key'])
                    content = json.loads(obj['Body'].read())
                    
                    # Take first record if it's an array
                    if isinstance(content, list):
                        content = content[0] if content else {}
                    
                    recent_data.append({
                        'key': file['Key'],
                        'size': file['Size'],
                        'last_modified': file['LastModified'].isoformat(),
                        'data': content
                    })
                except:
                    pass
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'pond_name': pond,
            'recent_data': recent_data,
            'timestamp': datetime.utcnow().isoformat()
        })
    }

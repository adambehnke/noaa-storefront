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
    
    # Get recent files from bronze layer - search last 3 days
    recent_data = []
    all_files = []
    
    for days_back in range(3):
        date = datetime.utcnow() - timedelta(days=days_back)
        year = date.strftime('%Y')
        month = date.strftime('%m')
        day = date.strftime('%d')
        
        # Try date partitioned path
        prefix = f'bronze/{pond}/*/year={year}/month={month}/day={day}/'
        
        try:
            response = s3.list_objects_v2(
                Bucket=BUCKET,
                Prefix=f'bronze/{pond}/',
                MaxKeys=1000
            )
            
            if 'Contents' in response:
                # Filter for today's files
                today_files = [
                    f for f in response['Contents'] 
                    if f'year={year}/month={month}/day={day}/' in f['Key']
                ]
                all_files.extend(today_files)
                
                if len(all_files) >= 10:
                    break
        except:
            pass
    
    # Sort by last modified, get 5 most recent
    if all_files:
        files = sorted(all_files, key=lambda x: x['LastModified'], reverse=True)[:5]
        
        for file in files:
            if file['Key'].endswith('.json') and file['Size'] < 100000:
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
                    print(f"Error reading {file['Key']}: {e}")
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'pond_name': pond,
            'recent_data': recent_data,
            'files_found': len(all_files),
            'timestamp': datetime.utcnow().isoformat()
        })
    }

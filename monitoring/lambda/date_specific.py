import json
import boto3
from datetime import datetime, timedelta

s3 = boto3.client('s3')
BUCKET = 'noaa-federated-lake-899626030376-dev'

def lambda_handler(event, context):
    params = event.get('queryStringParameters', {}) or {}
    pond = params.get('pond_name', '')
    
    if not pond:
        return {'statusCode': 400, 'body': json.dumps({'error': 'pond_name required'})}
    
    recent_data = []
    
    # Search today's and yesterday's data only
    for days_back in range(2):
        date = datetime.utcnow() - timedelta(days=days_back)
        year, month, day = date.strftime('%Y'), date.strftime('%m'), date.strftime('%d')
        
        # Search in each product type
        products = ['wind', 'water_level', 'water_temperature', 'air_temperature', 'air_pressure', 'stations']
        
        for product in products:
            prefix = f'bronze/{pond}/{product}/year={year}/month={month}/day={day}/'
            
            try:
                response = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix, MaxKeys=50)
                
                if 'Contents' in response:
                    files = sorted(response['Contents'], key=lambda x: x['LastModified'], reverse=True)
                    
                    for file in files[:2]:  # Take 2 per product
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
                                
                                if len(recent_data) >= 5:
                                    break
                            except:
                                pass
                if len(recent_data) >= 5:
                    break
            except:
                pass
        
        if len(recent_data) >= 5:
            break
    
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({
            'pond_name': pond,
            'recent_data': recent_data,
            'timestamp': datetime.utcnow().isoformat()
        })
    }

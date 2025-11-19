import json
import subprocess
import sys

def lambda_handler(event, context):
    """Lambda wrapper for ocean ingestion"""
    hours = event.get('hours_back', 1)
    env = event.get('env', 'dev')

    try:
        # Run the ingestion script
        result = subprocess.run(
            [sys.executable, 'quick_ocean_ingest.py', '--env', env, '--hours', str(hours)],
            capture_output=True,
            text=True,
            timeout=280
        )

        if result.returncode == 0:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'success',
                    'hours': hours,
                    'output': result.stdout[-500:]  # Last 500 chars
                })
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'status': 'failed',
                    'error': result.stderr[-500:]
                })
            }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'status': 'failed', 'error': str(e)})
        }

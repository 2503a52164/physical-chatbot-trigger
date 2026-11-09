import json
import os
import hmac
import uuid
import urllib3
import boto3
from decimal import Decimal
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
logs_table = dynamodb.Table('ButtonLogs')
config_table = dynamodb.Table('BotConfig')
http = urllib3.PoolManager()

# Secrets come from Lambda environment variables, not from the code
WEBHOOK_URL = os.environ['WEBHOOK_URL']
API_KEY = os.environ['API_KEY']


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    raise TypeError


def is_authorized(event):
    headers = event.get('headers') or {}
    supplied = headers.get('x-api-key', '')
    return hmac.compare_digest(supplied.encode('utf-8'), API_KEY.encode('utf-8'))


def lambda_handler(event, context):
    http_info = event.get('requestContext', {}).get('http', {})
    method = http_info.get('method', 'GET')

    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': '*'
    }

    if method == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}

    # Reading is open. Anything that changes data needs the key.
    if method in ('POST', 'DELETE') and not is_authorized(event):
        return {'statusCode': 401, 'headers': headers,
                'body': json.dumps({'error': 'Unauthorized'})}

    if method == 'GET':
        logs_res = logs_table.scan()
        config_res = config_table.scan()
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'logs': logs_res.get('Items', []),
                'configs': config_res.get('Items', [])
            }, default=decimal_default)
        }

    elif method == 'POST':
        body = json.loads(event.get('body') or '{}')
        action = body.get('action', 'UPDATE_CONFIG')
        device_id = body.get('device_id', 'esp32_button_1')

        if action == 'VIRTUAL_TRIGGER':
            timestamp = datetime.utcnow().isoformat() + "Z"
            res = config_table.get_item(Key={'device_id': device_id})
            bot_message = res.get('Item', {}).get('custom_message', 'Virtual Cloud Trigger Activated!')

            payload = {
                "content": f"⚡ **[Cloud Virtual Trigger]** {bot_message}\n*Device:* `{device_id}` | *Source:* `Web Command Center` | *Time:* `{timestamp}`"
            }
            resp = http.request('POST', WEBHOOK_URL, body=json.dumps(payload).encode('utf-8'),
                                headers={'Content-Type': 'application/json'})

            logs_table.put_item(Item={
                'press_id': str(uuid.uuid4()),
                'device_id': device_id,
                'timestamp': timestamp,
                'message_sent': bot_message,
                'trigger_source': 'CLOUD_DASHBOARD',
                'webhook_status': resp.status
            })
            return {'statusCode': 200, 'headers': headers,
                    'body': json.dumps({'status': 'Virtual trigger sent!'})}

        new_message = body.get('custom_message', 'Updated message from Cloud Command Center!')
        config_table.put_item(Item={'device_id': device_id, 'custom_message': new_message})
        return {'statusCode': 200, 'headers': headers,
                'body': json.dumps({'status': 'Configuration saved!', 'new_message': new_message})}

    elif method == 'DELETE':
        scan = logs_table.scan()
        with logs_table.batch_writer() as batch:
            for each in scan.get('Items', []):
                batch.delete_item(Key={'press_id': each['press_id']})
        return {'statusCode': 200, 'headers': headers,
                'body': json.dumps({'status': 'All logs cleared!'})}

    return {'statusCode': 405, 'headers': headers,
            'body': json.dumps({'error': 'Method not allowed'})}

import json
import os
import urllib3
import boto3
import uuid
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
logs_table = dynamodb.Table('ButtonLogs')
config_table = dynamodb.Table('BotConfig')
http = urllib3.PoolManager()

# Secret comes from the Lambda environment variable, not from the code
WEBHOOK_URL = os.environ['WEBHOOK_URL']


def lambda_handler(event, context):
    device_id = event.get('device_id', 'esp32_button_1')
    timestamp = datetime.utcnow().isoformat() + "Z"

    # 1. Fetch the custom message from the BotConfig table
    try:
        res = config_table.get_item(Key={'device_id': device_id})
        bot_message = res.get('Item', {}).get('custom_message', 'Hello from ESP32 Physical Button!')
    except Exception:
        bot_message = "Button pressed! (Default fallback message)"

    # 2. Send the message to Discord
    payload = {
        "content": f"**[Physical Trigger]** {bot_message}\n*Device:* `{device_id}` | *Time:* `{timestamp}`"
    }
    encoded_payload = json.dumps(payload).encode('utf-8')
    resp = http.request('POST', WEBHOOK_URL, body=encoded_payload,
                        headers={'Content-Type': 'application/json'})

    # 3. Log the event in DynamoDB
    logs_table.put_item(
        Item={
            'press_id': str(uuid.uuid4()),
            'device_id': device_id,
            'timestamp': timestamp,
            'message_sent': bot_message,
            'webhook_status': resp.status
        }
    )

    return {
        'statusCode': 200,
        'body': json.dumps('Message sent and logged successfully!')
    }

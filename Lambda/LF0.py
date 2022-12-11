import json
import boto3
from datetime import datetime


def lambda_handler(event, context):
    lexv2 = boto3.client('lexv2-runtime')

    if event["body"] is not None:
        user_body = json.loads(event["body"])
        user_msg = user_body["messages"][0]["unstructured"]["text"]
        response = lexv2.recognize_text(
            botId='R1IN457OIP',
            botAliasId='TSTALIASID',
            localeId='en_US',
            sessionId='test-session',
            text=user_msg)
        print(response)
        responseMessages = response['messages']
    else:
        responseMessages = None

    messages = []
    timestamp = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    if responseMessages:
        for msg in responseMessages:
            message = {
                "type": "unstructured",
                "unstructured": {
                    "id": "test",
                    "text": msg["content"],
                    "timestamp": timestamp
                }
            }
            messages.append(message)

    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
        },
        'body': json.dumps({"messages": messages})
    }

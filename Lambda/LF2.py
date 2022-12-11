import json
import boto3
from boto3.dynamodb.conditions import Key
from opensearchpy import OpenSearch, RequestsHttpConnection
from aws_requests_auth.aws_auth import AWSRequestsAuth
import logging

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

opensearch_host = 'search-restaurants-htepsafc3azh35lff6op3enioq.us-east-1.es.amazonaws.com'
region = 'us-east-1'


def poll_sqs():
    sqs = boto3.client('sqs')
    queue_url = 'https://sqs.us-east-1.amazonaws.com/036195788069/queue'
    response = sqs.receive_message(
        QueueUrl=queue_url,
        VisibilityTimeout=0,
        WaitTimeSeconds=0)

    if 'Messages' in response:
        message = response['Messages'][0]
        info = json.loads(message['Body'])

        receipt_handle = message['ReceiptHandle']
        sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle)
        logger.debug('Message retrieved from SQS.')
        return info
    else:
        logger.debug('No message in SQS.')
        return None


def build_search_client(host, port=443):
    credentials = boto3.Session().get_credentials()
    service = "es"
    awsauth = AWSRequestsAuth(
        aws_access_key=credentials.access_key,
        aws_secret_access_key=credentials.secret_key,
        aws_token=credentials.token,
        aws_host=opensearch_host,
        aws_region=region,
        aws_service=service
    )
    client = OpenSearch(
        hosts=[{'host': host, 'port': port}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    return client


def search_cuisine(client, cuisine):
    query = {
        'size': 3,
        'query': {
            'function_score': {
                'query': {
                    'multi_match': {
                        'query': cuisine,
                        'fields': ['businessId', 'cuisine'],
                    }
                },
                'random_score': {}
            },

        }
    }
    opensearch_rsp = client.search(body=query, index='restaurant')
    businesses = opensearch_rsp['hits']['hits']
    id_list = []
    for business in businesses:
        id_list.append(business['_source']['businessId'])
    return id_list


def search_dynamodb(info, businessIds):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('yelp-restaurants')
    text = 'Hello! Here are my {0} restaurant suggestions for {1} people, for {2} at {3}: '.format(info['Cuisine'],
                                                                                                   info['PeopleNumber'],
                                                                                                   info['Date'],
                                                                                                   info['Time'])
    for i, businessId in enumerate(businessIds):
        dynamodb_rsp = table.query(
            KeyConditionExpression=Key('businessId').eq(businessId)
        )
        restaurant = dynamodb_rsp['Items'][0]
        name = restaurant['name']
        temp = '{0}. {1}, '.format(str(i + 1), name)
        if restaurant['address']:
            address = restaurant['address']
            temp += 'located at ' + address + " "
        text += temp
    return text


def sentEmail(addr, msg):
    body = msg 
    client = boto3.client('ses')
    response = client.send_email(
        Destination={
            'ToAddresses': [
                addr,
            ],
        },
        Message={
            'Body': {
                'Text': {
                    'Charset': 'UTF-8',
                    'Data': (body),
                },
            },
            'Subject': {
                'Charset': 'UTF-8',
                'Data': "Your reccomendations",
            },
        },
        Source="shiboshengs2@gmail.com",
    )
    print("Sent")


def lambda_handler(event, context):
    info = poll_sqs()
    if info:
        #phone = '+1' + info['Phone']
        email = info['email']
        opensearch = build_search_client(opensearch_host)
        businessIds = search_cuisine(opensearch, info['Cuisine'])
        text = search_dynamodb(info, businessIds)
        sentEmail(email, text)

    return 200

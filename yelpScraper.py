import requests
import json
from datetime import datetime
import boto3
from boto3.dynamodb.conditions import Key
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

yelp_key = "HNOkS63Q7v5ski_gY7xF6lBzNBwNgaNBsGCB4-XhOSAK-hsLY8FqEyUt3Eguq9m1Q_QxNagyCdLZ5faHhL6in5ZYsvsVzlV-b0mAd6dYmwF9C4k5Jg-tGcUlDyk6Y3Yx"
opensearch_host = "search-restaurants-htepsafc3azh35lff6op3enioq.us-east-1.es.amazonaws.com"
region = "us-east-1"

def build_search_client(host, port=443):
    service = "es"
    credentials = boto3.Session().get_credentials()
    awsauth = AWS4Auth('AKIAQQ3LP4USU43VTMHR', '29fBf/Fg4ddotmlQPqI99BM+1ueL4rwQOqzcFjzL', region, service, None)

    client = OpenSearch(
        hosts=[{'host': host, 'port': port}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    return client



def main():
    dynamodb = boto3.resource("dynamodb", region_name='us-east-1', aws_access_key_id='AKIAQQ3LP4USU43VTMHR', aws_secret_access_key='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')
    table = dynamodb.Table("yelp-restaurants")
    opensearch = build_search_client(opensearch_host)
    index_name = "restaurant"
    index_body = {
        "mappings": {
            "properties": {
                "businessId": {"type": "text"},
                "cuisine": {"type": "text"}
            }
        }
    }
    opensearch.indices.create(index_name, body=index_body)

    cuisines = ["American", "French", "Chinese", "Japanese", "Indian", "Mexican"]
    url = "https://api.yelp.com/v3/businesses/search"
    headers = {"Authorization": "Bearer " + yelp_key}

    for cuisine in cuisines:
        term = cuisine + " restaurant"
        for offset in range(0, 1000, 50):
            payload = {
                "term": term,
                "location": "New York",
                "limit": 50,
                "offset": offset
            }
            response = requests.get(url=url, headers=headers, params=payload)
            response = json.loads(response.text)
            for business in response["businesses"]:
                document = {
                    "businessId": business["id"],
                    "cuisine": cuisine
                }
                opensearch.index(
                    index="restaurant",
                    body=document,
                    refresh=True
                )

                item = {
                    "businessId": business["id"],
                    "insertedAtTimestamp": datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
                }
                if business["name"]:
                    item["name"] = business["name"]
                if business["location"]["address1"]:
                    item["address"] = business["location"]["address1"]
                if business["coordinates"]:
                    item["coordinates"] = "(" + str(business["coordinates"]["latitude"]) + ", " + str(business["coordinates"]["longitude"]) + ")"
                if business["review_count"]:
                    item["reviewNum"] = str(business["review_count"])
                if business["rating"]:
                    item["rating"] = str(business["rating"])
                if business["location"]["zip_code"]:
                    item["zipCode"] = business["location"]["zip_code"]
                table.put_item(Item=item)

main()
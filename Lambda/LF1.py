import json
import datetime
import time
import os
import dateutil.parser
import dateutil.utils
from datetime import datetime
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


# --- Helpers that build all of the responses ---


def elicit_slot(intent_name, slots, slot_to_elicit, message):
    return {
        'sessionState': {
            'dialogAction': {
                'type': 'ElicitSlot',
                'slotToElicit': slot_to_elicit
            },
            'intent': {
                'name': intent_name,
                'slots': slots,
                'state': 'Failed'
            }
        },
        'messages': [message]
    }


def close(intent_name, message):
    return {
        'sessionState': {
            'dialogAction': {
                'type': 'Close',
            },
            'intent': {
                'name': intent_name,
                'state': 'Fulfilled'
            }
        },
        'message': [message]
    }


def delegate(intent_name, slots):
    return {
        'sessionState': {
            'dialogAction': {
                'type': 'Delegate',
            },
            'intent': {
                'name': intent_name,
                'slots': slots,
                'state': 'ReadyForFulfillment'
            }
        }

    }


# --- Helper Functions ---


def safe_int(n):
    """
    Safely convert n value to int.
    """
    if n is not None:
        return int(n)
    return n


def try_ex(func):
    """
    Call passed in function in try block. If KeyError is encountered return None.
    This function is intended to be used to safely access dictionary.

    Note that this function would have negative impact on performance.
    """

    try:
        return func()
    except TypeError:
        return None


def isvalid_location(location):
    valid_locations = ['new york', 'manhattan', 'flushing', 'jersey']
    return location.lower() in valid_locations


def isvalid_date(date):
    try:
        date = dateutil.parser.parse(date)
        if date < dateutil.utils.today():
            return False
        return True
    except ValueError:
        return False


def isvalid_time(date, time):
    try:
        date = dateutil.parser.parse(date).date()
        time = dateutil.parser.parse(time).time()
        if datetime.combine(date, time) < datetime.now():
            return False
        return True
    except ValueError:
        return False


def isvalid_cuisine(cuisine):
    valid_cuisines = ['chinese', 'japanese', 'american', 'french', 'indian', 'mexican']
    return cuisine.lower() in valid_cuisines


def isvalid_email(email):
    valid_email = ["ss6372@columbia.edu", "shiboshengs2@gmail.com"]
    return email.lower() in valid_email


def build_validation_result(isvalid, violated_slot, message_content):
    return {
        'isValid': isvalid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }


def validate_restaurant(slots):
    location = try_ex(lambda: slots['City']['value']['interpretedValue'])
    cuisine = try_ex(lambda: slots['Cuisine']['value']['interpretedValue'])
    peopleNumber = try_ex(lambda: slots['PeopleNumber']['value']['interpretedValue'])
    date = try_ex(lambda: slots['Date']['value']['interpretedValue'])
    time = try_ex(lambda: slots['Time']['value']['interpretedValue'])
    phone = try_ex(lambda: slots['Phone']['value']['interpretedValue'])
    email = try_ex(lambda: slots['email']['value']['interpretedValue'])

    if location and not isvalid_location(location):
        return build_validation_result(
            False,
            'City',
            'We currently do not support this area. Can you try a different area?'.format(location)
        )

    if cuisine and not isvalid_cuisine(cuisine):
        return build_validation_result(
            False,
            'Cuisine',
            'We currently do not support this genre of food now. Can you try a different cuisine type?'.format(cuisine)
        )

    if date and not isvalid_date(date):
        return build_validation_result(
            False,
            'Date',
            'Please enter a valid date.'
        )

    if date and time and not isvalid_time(date, time):
        return build_validation_result(
            False,
            'Time',
            'Please enter a valid time.'
        )

    if email and not isvalid_email(email):
        return build_validation_result(
            False,
            'email',
            'This email is not in the whitelist. Please provide a valid email or contact the administrator.'
        )

    return {'isValid': True}


# --- Functions that communicate with backend ---


def push_sqs(text):
    sqs = boto3.client('sqs')
    queue_url = 'https://sqs.us-east-1.amazonaws.com/036195788069/queue'
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=text)


# --- Functions that control the bot's behavior ---


def suggest_restaurant(intent_request):
    """
    Performs dialog management and fulfillment for booking a hotel.

    Beyond fulfillment, the implementation for this intent demonstrates the following:
    1) Use of elicitSlot in slot validation and re-prompting
    2) Use of requestAttributes to pass information that can be used to guide conversation
    """
    location = try_ex(
        lambda: intent_request['sessionState']['intent']['slots']['City']['value']['interpretedValue'])
    cuisine = try_ex(lambda: intent_request['sessionState']['intent']['slots']['Cuisine']['value']['interpretedValue'])
    peopleNumber = try_ex(
        lambda: intent_request['sessionState']['intent']['slots']['PeopleNumber']['value']['interpretedValue'])
    date = try_ex(lambda: intent_request['sessionState']['intent']['slots']['Date']['value']['interpretedValue'])
    time = try_ex(lambda: intent_request['sessionState']['intent']['slots']['Time']['value']['interpretedValue'])
    phone = try_ex(lambda: intent_request['sessionState']['intent']['slots']['Phone']['value']['interpretedValue'])
    email = try_ex(lambda: intent_request['sessionState']['intent']['slots']['email']['value']['interpretedValue'])

    # Load confirmation history and track the current reservation.
    sqsSend = json.dumps({
        'City': location,
        'Cuisine': cuisine,
        'PeopleNumber': peopleNumber,
        'Date': date,
        'Time': time,
        'Phone': phone,
        'email': email
    })


    if intent_request['invocationSource'] == 'DialogCodeHook':
        # Validate any slots which have been specified. If any are invalid, re-elicit for their value
        validation_result = validate_restaurant(intent_request['sessionState']['intent']['slots'])
        if not validation_result['isValid']:
            slots = intent_request['sessionState']['intent']['slots']
            slots[validation_result['violatedSlot']] = None

            return elicit_slot(
                intent_request['sessionState']['intent']['name'],
                slots,
                validation_result['violatedSlot'],
                validation_result['message']
            )

        if location and cuisine and peopleNumber and date and time and phone:
            push_sqs(sqsSend)
        return delegate(intent_request['sessionState']['intent']['name'],
                        intent_request['sessionState']['intent']['slots'])


# --- Intents ---


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug('dispatch intentName={}'.format(intent_request['sessionState']['intent']['name']))
    intent_name = intent_request['sessionState']['intent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'testBot':
        return suggest_restaurant(intent_request)
    raise Exception('Intent with name ' + intent_name + ' not supported')


# --- Main handler ---


def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))

    return dispatch(event)

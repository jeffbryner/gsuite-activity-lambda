import boto3
import json
import os
import logging
from botocore.exceptions import ClientError
from datetime import datetime,timedelta
from utils.helpers import chunks
from utils.dates import utcnow
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials

logger = logging.getLogger()
logger.setLevel(logging.INFO)

FIREHOSE_DELIVERY_STREAM= os.environ.get('FIREHOSE_DELIVERY_STREAM','test')
FIREHOSE_BATCH_SIZE=os.environ.get('FIREHOSE_BATCH_SIZE',100)
GSUITE_CREDENTIALS_SECRET_NAME=os.environ.get('GSUITE_CREDENTIALS_SECRET_NAME','unknown')
SCOPES = ['https://www.googleapis.com/auth/admin.reports.audit.readonly']
GSUITE_DELEGATED_ACCOUNT=os.environ.get('GSUITE_DELEGATED_ACCOUNT','someone@somewhere.com')
ssmclient=boto3.client('ssm')
secrets_manager = boto3.client('secretsmanager')
f_hose = boto3.client('firehose')

def get_parameter(parameter_name,default):
    try:
        return(ssmclient.get_parameter(Name=parameter_name)["Parameter"]['Value'])
    except ClientError as e:
        if e.response['Error']['Code'] == 'ParameterNotFound':
            return default

def put_parameter(parameter_name,value):
    ssmclient.put_parameter(Name=parameter_name,Type='String',Value=value,Overwrite=True)

def send_to_firehose(records):
    # records should be a list of dicts
    if type(records) is list:
        # batch up the list below the limits of firehose
        for batch in chunks(records,FIREHOSE_BATCH_SIZE):
            response = f_hose.put_record_batch(
                DeliveryStreamName=FIREHOSE_DELIVERY_STREAM,
                Records=[{'Data': bytes(str(json.dumps(record)+'\n').encode('UTF-8'))} for record in batch]
            )
            logger.debug('firehose response is: {}'.format(response))

def handler(event,context):
    # get the gsuite credentials
    credentials = json.loads(secrets_manager.get_secret_value(SecretId=GSUITE_CREDENTIALS_SECRET_NAME)["SecretString"])
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials, SCOPES)
    # delegate to an account (should be super user with permisisons to run activity reports)
    credentials = credentials.create_delegated(GSUITE_DELEGATED_ACCOUNT)
    # get events since last time we ran (default an hour ago)
    since=get_parameter('/gsuite-events/lastquerytime',(utcnow()-timedelta(minutes=60)).isoformat())
    logger.info(f"Looking for records since: {since}")
    service = build('admin', 'reports_v1', credentials=credentials,cache_discovery=False)

    next_page=True
    page_token=None
    last_run_time=utcnow().isoformat()
    while next_page:
        results = service.activities().list(userKey='all',
                                            applicationName='login',
                                            maxResults=1000,
                                            startTime=since,
                                            pageToken=page_token,
                                        ).execute()
        records = results.get('items', [])
        logger.info(f"sending: {len(records)} gsuite records to firehose")
        if records:
            send_to_firehose(records)
        if "nextPageToken" not in results:
            next_page=False
        else:
            page_token=results["nextPageToken"]

    put_parameter('/gsuite-events/lastquerytime',last_run_time)

# gsuite-activity-lambda
An aws lambda to grab gsuite activity logs and ship them to firehose.

Uses secrets manager and parameter store to access Gsuite project credentials to pull activity logs
and ship them to a firehose stream that you specify. 

Environment variables: 
FIREHOSE_DELIVERY_STREAM: Name of the delivery stream
GSUITE_CREDENTIALS_SECRET_NAME: Name of the credentials in secrets manager
GSUITE_DELEGATED_ACCOUNT: email@company.com that you want this to use for delegated access
FIREHOSE_BATCH_SIZE: number of records to batch send to firehose at a time (100 default)

###########################################################################
# This Makefile shows how to install and test the Lambda function and
# documents the preconditions necessary to invoke the function  either
# locally or on Lambda.
#
# To install and test the Lambda function, run the following commands:
#     $ make create_role
#     $ make create_function
#     $ make upload_config
#     $ make create_rule
#
# To test the Lambda handler by invoking it on AWS
#     $ make test
#
# To test the Lambda handler by invoking it locally
#     $ make localtest
#
###########################################################################

# Some credentials/configuration necessary to run are stored in secure
# storage to prevent disclosure of sensitive info.  The program 'creds'
# gets a value from secure storage.  Replace the calls to 'creds' below
# with your actual values.

# The AWS profile name to use in ~/.aws/credentials
PROFILE     := $(shell creds get EM247 aws_profile)

# The AWS region in which to run
REGION      := $(shell creds get EM247 aws_region)

# S3 bucket name containing configuration file for notifier.py
CFG_BUCKET  := $(shell creds get EM247 notify_cfg_bucket)

# Name of configuration file in the S3 bucket (e.g., 'notifier.yml')
CFG_NAME    := $(shell creds get EM247 notify_cfg_file)

# Define the environment variables that will be present when the
# function is invoked by Lambda.  These are passed in as a JSON string
# to lambda-uploader.
VBLS := '{"BUCKET_NAME": "$(CFG_BUCKET)", "KEY_NAME": "$(CFG_NAME)"}'

# Name of IAM role specifying permissions granted to Lambda function.
ROLE_NAME  := EM247-Lambda

# Name to be used when creating the function in Lambda.  
# The name is hardcoded in lambda.json.
LFUNC_NAME := $(shell grep '"name"' lambda.json | cut -f 4 -d '"')

# Name of IOT rule which invokes Lambda hander on button press
RULE_NAME  := EM247ButtonPressRule

# Serial number of IoT button that will be monitored
SERIAL_NUMBER = $(shell creds get EM247 serial_number)


# Step 1
create_role:
	@echo "Creating IAM role for Lambda function"
	./helper.py create-role $(ROLE_NAME) $(PROFILE)


# Step 2
# Note: as of 12/20/2016, the version of lambda-uploader in PyPi does not
# support '--variables'.  I used commit '1fae1bd' from github, which does support it.
# The role created in Step 1 must exist before running Step 2.
create_function:
	@echo "Creating and uploading Lambda function"
	lambda-uploader --profile=$(PROFILE)\
                        --variables=$(VBLS)\
	                --role=$(shell ./helper.py get-role-arn $(ROLE_NAME) $(PROFILE))


# Step 3
# Validate the config file.
validate_config:
	@echo "Validate config file syntax"
	export BUCKET_NAME=$(CFG_BUCKET);\
	export KEY_NAME=$(CFG_NAME);\
	untabify $(NOTIFY_CFG);\
	./notifier.py config validate --path=$(NOTIFY_CFG)


# Step 4
# Upload the notifier config file which defines how notifications are sent.
# Replace notifier-EM247.yml with your notifier.yml file.
NOTIFY_CFG := notifier-EM247.yml
upload_config:
	@echo "Uploading config for Lambda function"
	export BUCKET_NAME=$(CFG_BUCKET);\
	export KEY_NAME=$(CFG_NAME);\
	untabify $(NOTIFY_CFG);\
	./notifier.py config upload --profile=$(PROFILE) --path=$(NOTIFY_CFG)


# Step 5
# Create an IOT Rule that will invoke the Lambda handler from Step 2
# when an IoT Button with the specified serial number is pressed.
create_rule:
	@echo "Creating IoT Rule to call Lambda function on button press"
	./helper.py create-topic-rule $(RULE_NAME) $(LFUNC_NAME) $(SERIAL_NUMBER) $(PROFILE)


# Step 6
# Test the function by invoking from the AWS CLI.
IOTBUTTON_EVENT := '{"serialNumber": "'$(SERIAL_NUMBER)'", "clickType": "SINGLE", "batteryVoltage": "1975 mV"}'
lambdatest:
	@echo "Invoking the Lambda function"
	aws lambda invoke\
	    --invocation-type RequestResponse\
            --function-name $(LFUNC_NAME)\
	    --region=$(REGION)\
	    --profile=$(PROFILE)\
	    --payload=$(IOTBUTTON_EVENT)\
	    --log-type Tail\
            invocation_log.txt


# Run the notification function locally for testing purposes.
# Although invoked locally, notifier.py uses the config stored on S3
# in the bucket/filename specified in the environment variables,
# and it uses the provided AWS profile to get S3 read permissions.
localtest:
	@echo "Invoking function locally"
	export BUCKET_NAME=$(CFG_BUCKET);\
	export KEY_NAME=$(CFG_NAME);\
	./notifier.py sendmessages --profile=$(PROFILE)

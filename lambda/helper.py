#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''Usage:
    helper [options] create-role (ROLE-NAME) (PROFILE-NAME)
    helper [options] get-role-arn (ROLE-NAME) (PROFILE-NAME)
    helper [options] get-function-arn (FUNCTION-NAME) (PROFILE-NAME)
    helper [options] create-topic-rule (RULE-NAME) (FUNCTION-NAME) (SERIAL-NUMBER) (PROFILE-NAME)

    create-role - Create IAM role named ROLE-NAME.
    get-role-arn - Get ARN of the IAM role named ROLE-NAME.
    get-function-arn - Get ARN of Lambda function named FUNCTION-NAME
    create-topic-rule - Create IOT rule name RULE-NAME which invokes a
                        Lambda function named FUNCTION-NAME when the
                        IoT Button with serial number SERIAL-NUMBER is pressed.

    This is example code - not production code - there is no error handling.

Options:
    --V   - Set debug level to Info
    --VV  - Set debug level to Debug

'''

from __future__ import print_function

import json
import logging

import boto3
import docopt
import dotmap


logger = None


class AWS_IAM(object):


    def __init__(self, aws_profile):

        self.aws_profile = aws_profile
        self.session = boto3.Session(profile_name=self.aws_profile)
        self.client = self.session.client('iam')


    def create_role(self, role_name):

        # Step 1
        # Create IAM role that Lambda can assume upon execution.
        role = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "lambda.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        trust_policy_document = json.dumps(role)
        resp = self.client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=trust_policy_document)

        # Step 2
        # Attach Policy to Role granting read-only access to S3.
        # Attach Policy to Role granting Lambda write access to logging.
        policy_Arns = [
            'arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess',
            'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
        ]
        for policy_Arn in policy_Arns:
            resp = self.client.attach_role_policy(
                RoleName=role_name,
                PolicyArn=policy_Arn)


    def get_role_arn(self, role_name):
        resp = self.client.get_role(RoleName=role_name)
        role_arn = resp['Role']['Arn']
        return role_arn


class AWS_IOT(object):


    def __init__(self, aws_profile):

        self.aws_profile = aws_profile
        self.session = boto3.Session(profile_name=self.aws_profile)
        self.client = self.session.client('iot')


    def create_topic_rule(self, rule_name, function_name, serial_number):

        aws_lambda = AWS_Lambda(self.aws_profile)

        rule_payload = {
            'sql': "SELECT * FROM 'iotbutton/%s'" % serial_number,
            'description': 'EM247 Button Press Rule',
            'actions': [
                {
                    'lambda': {
                        'functionArn': aws_lambda.get_function_arn(function_name),
                    },
                },
            ],
            'ruleDisabled': False,
            'awsIotSqlVersion': '2016-03-23',
        }
        resp = self.client.create_topic_rule(ruleName=rule_name,
                                             topicRulePayload=rule_payload)


class AWS_Lambda(object):


    def __init__(self, aws_profile):

        self.aws_profile = aws_profile
        self.session = boto3.Session(profile_name=self.aws_profile)
        self.client = self.session.client('lambda')


    def get_function(self, function_name):
        resp = self.client.get_function(FunctionName=function_name)
        return resp


    def get_function_arn(self, function_name):
        resp = self.get_function(function_name)
        function_arn = resp['Configuration']['FunctionArn']
        return function_arn


def setup_logging(args):

    logger = logging.getLogger('')

    if args.V:
        logger.setLevel(logging.INFO)
    elif args.VV:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)

    handler = logging.StreamHandler()
    fmt = '%(levelname)s:%(filename)s:%(lineno)s:%(funcName)s:%(message)s'
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)



if __name__ == '__main__':


    import logging
    import sys
    from logging_tree import printout

    args = docopt.docopt(__doc__, version='v 1.0')
    args = {k.replace('-', '') : args[k] for k in args.keys()}
    args = dotmap.DotMap(args)

    setup_logging(args)

    if args.createrole:
        aws_iam = AWS_IAM(args.PROFILENAME)
        aws_iam.create_role(args.ROLENAME)
    elif args.getrolearn:
        aws_iam = AWS_IAM(args.PROFILENAME)
        arn = aws_iam.get_role_arn(args.ROLENAME)
        print(arn)
    elif args.getfunctionarn:
        aws_lambda = AWS_Lambda(args.PROFILENAME)
        arn = aws_lambda.get_function_arn(args.FUNCTIONNAME)
        print(arn)
    elif args.createtopicrule:
        aws_iot = AWS_IOT(args.PROFILENAME)
        aws_iot.create_topic_rule(args.RULENAME, args.FUNCTIONNAME, args.SERIALNUMBER)
    else:
        print(docopt.docopt.printable_usage(__doc__))
        sys.exit(1)

    sys.exit(0)


#;;; Local Variables:
#;;; mode: python
#;;; coding: utf-8
#;;; eval: (auto-fill-mode)
#;;; eval: (set-fill-column 78)
#;;; eval: (fci-mode)
#;;; End:
   

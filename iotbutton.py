#!/usr/bin/env python
# -*- coding: utf-8 -*-


import json
import logging
import os
import pdb
import re
import requests

import boto3

from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

import common


logger = None


class AWSIoTButton(object):

    rootCA_filename = 'aws-iot-rootCA.pem'
    rootCA_url = ('''https://www.symantec.com/content/en/us/enterprise/verisign/roots/'''
                  '''VeriSign-Class 3-Public-Primary-Certification-Authority-G5.pem''')

    awsiot_endpoint = None

    thing_type_name = 'EM247ButtonT'
    thing_type_description = 'EM247 IoT Button'
    thing_type_searchable_attributes = ['serialNumber',]

    policy_name = 'EM247PubSub'

    rule_name = 'EM247InvokeClickHandler'
    rule_description = 'Invoke message handler when button clicked.'

    # Name of Lambda function/handler
    function_name = 'EMS247-Notifier'

    mqtt_client_id = 'iotbuttonclicksim'

    _endpoint = None


    def __init__(self, certs_dir, rootCA_filename, profile_name, serial_num=None):
        '''
        Args:
            certs_dir (string) - pathname to a directory in which to store
                the root CA as well as any certs that are created.

            rootCA_filename (string) - filename in which to store the root
                CA for AWS IoT.  The file is stored in certs_dir.

        '''
        self.certs_dir = os.path.expanduser(certs_dir)
        self.rootCA_pathname = os.path.join(self.certs_dir, rootCA_filename)
        self._ensure_rootCA()
        self.session = boto3.Session(profile_name=profile_name)
        self.client = self.session.client('iot')
        self.lambda_client = self.session.client('lambda')
        self.serial_num = serial_num


    def _ensure_rootCA(self):
        '''If not already present, download the AWS IoT root CA.'''
        if not os.path.isfile(self.rootCA_pathname):
            common.makedirs(self.certs_dir, exists_ok=True)
            result = requests.get(self.rootCA_url)
            rootCA_file = open(self.rootCA_pathname, 'wb')
            rootCA_file.write(result.content)
            rootCA_file.close()


    def create_thing_type(self):
        '''Create a Thing Type that will be associated with the Thing.'''
        resp = self.client.create_thing_type(
            thingTypeName=self.thing_type_name,
            thingTypeProperties={
                'thingTypeDescription': self.thing_type_description,
                'searchableAttributes': self.thing_type_searchable_attributes,
                }
            )
        return resp


    def create_policy(self):
        '''Create a policy granting full access.'''
        policyDocument={
            'Version': '2012-10-17',
            'Statement': [{
                'Effect': 'Allow',
                'Action': ['iot:*'],
                'Resource': ['*'],
            }]
        }
        policyDocument = json.dumps(policyDocument)
        resp = self.client.create_policy(policyName=self.policy_name,
                                         policyDocument=policyDocument)
        return resp


    def create_thing(self, serial_num):
        self.serial_num = serial_num
        resp = self.client.create_thing(
            thingName=self.thing_name,
            thingTypeName=self.thing_type_name,
            attributePayload={
                'attributes': self.thing_attributes,
                'merge': False
                }
            )
        return resp


    def create_keys_and_certificate(self, serial_num):
        '''Create the security credentials that will allow the Button to connect
        to the IoT endpoing.  This overwrites any existing certs for the Button.
        The certificate is identifed by an ARN, which is saved in a text file.
        '''
        self.serial_num = serial_num
        resp = self.client.create_keys_and_certificate(setAsActive=True)
        common.makedirs(self.certs_dir, exists_ok=True)
        open(self.certificate, 'wb').write(resp['certificatePem'])
        open(self.certificate_arn_pathname, 'wb').write(resp['certificateArn'])

        open(self.public_key, 'wb').write(resp['keyPair']['PublicKey'])
        open(self.private_key, 'wb').write(resp['keyPair']['PrivateKey'])
        return resp


    @property
    def certificate_arn(self):
        ''''Returns a string containing the ARN for the certificate for
        this button.  Will look something like this:
            'arn:aws:iot:us-west-2:858768675439:cert/69b79...f2f574526'
        '''
        arn = open(self.certificate_arn_pathname, 'rb').read()
        return re.sub(r'\n', '', arn)


    def attach_principal_policy(self, serial_num):
        self.serial_num = serial_num
        resp = self.client.attach_principal_policy(
            policyName=self.policy_name,
            principal=self.certificate_arn)
        return resp


    def attach_thing_principal(self, serial_num):
        '''Attaches the Thing/Button to the security Principal.'''
        self.serial_num = serial_num
        resp = self.client.attach_thing_principal(
            thingName=self.thing_name, 
            principal=self.certificate_arn
        )
        return resp


    @property
    def function_arn(self):
        '''Returns a string containing the ARN for the Lambda Handler.

        '''
        resp = self.lambda_client.get_function(FunctionName=self.function_name)
        return resp['Configuration']['FunctionArn']


    @property
    def thing_name(self):
        return 'iotbutton_%s' % self.serial_num


    @property
    def thing_attributes(self):
        return {'serialNumber': self.serial_num}


    @property
    def private_key(self):
        return os.path.join(self.certs_dir, '%s-private-key.pem' % self.serial_num)


    @property
    def public_key(self):
        return os.path.join(self.certs_dir, '%s-public-key.pem' % self.serial_num)


    @property
    def certificate(self):
        return os.path.join(self.certs_dir, '%s-cert.pem' % self.serial_num)


    @property
    def certificate_arn_pathname(self):
        return os.path.join(self.certs_dir, '%s-arn.txt' % self.serial_num)


    def get_endpoint(self):
        resp = self.client.describe_endpoint()
        return resp['endpointAddress']


    @property
    def endpoint(self):
        if not self._endpoint:
            self._endpoint = self.get_endpoint()
        return self._endpoint


    def one_shot(self, serial_num):
        resp1 = self.create_thing(serial_num)
        resp2 = self.create_keys_and_certificates(serial_num)
        resp3 = self.attach_principal_policy(serial_num)
        resp4 = self.attach_thing_principal(serial_num)
        return (resp1, resp2, resp3, resp4)
        

    def payload(self, voltage, click_type):
        '''Return a payload to be sent back to AWS IoT when simulating
        a button press.  The payload is a string containing a JSON
        data structure.
        '''
        pload = dict(serialNumber=self.serial_num,
                     batteryVoltage=voltage,
                     clickType=click_type)
        pload = json.dumps(pload)
        return pload


    @property
    def topic(self):
        topic_format = 'iotbutton/{serial_num}'
        return topic_format.format(serial_num=self.serial_num)


    def _init_mqtt_client(self):

        myMQTTClient = AWSIoTMQTTClient(self.mqtt_client_id)
        myMQTTClient.configureEndpoint(self.endpoint, 8883)
        myMQTTClient.configureCredentials(self.rootCA_pathname,
                                          self.private_key,
                                          self.certificate)
        myMQTTClient.configureOfflinePublishQueueing(-1)
        myMQTTClient.configureDrainingFrequency(2)
        myMQTTClient.configureConnectDisconnectTimeout(10)
        myMQTTClient.configureMQTTOperationTimeout(5)
        return myMQTTClient


    def click(self, serial_num, click_type, voltage='9999mV'):
        self.serial_num = serial_num
        if (click_type not in ['SINGLE', 'DOUBLE', 'LONG'] or 
            not re.match(r'(?i)^\d{4}mV$', voltage)):
           raise ValueError
        mqtt_client = self._init_mqtt_client()
        payload = self.payload(click_type=click_type, voltage=voltage)
        mqtt_client.connect()
        mqtt_client.publish(self.topic, payload, 0)
        mqtt_client.disconnect()


    def set_serial_num(self, serial_num):
        self.serial_num = serial_num

            
    def create_topic_rule(self, serial_num):
        pdb.set_trace()
        self.serial_num = serial_num
        resp = self.client.create_topic_rule(
            ruleName=self.rule_name,
            topicRulePayload={
                'sql': "SELECT * FROM '%s'" % self.topic,
                'description': self.rule_description,
                'actions': [
                    {
                        'lambda': {
                            'functionArn': self.function_arn,
                        }
                    },
                ],
                'ruleDisabled': False,
                'awsIoTSqlVersion': "2016-03-23"
            }
        )
        return resp


    

#;;; Local Variables:
#;;; mode: python
#;;; coding: utf-8
#;;; eval: (auto-fill-mode)
#;;; eval: (set-fill-column 78)
#;;; eval: (fci-mode)
#;;; End:

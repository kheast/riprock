#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''Simple Lambda function that performs voice and SMS notifications.
Uses Twilio for both forms of notification;  requires a valid Twilio
account to use.

This code is designed to run either a) when invoked by Lambda, or b)
when invoked from the commandline on a development machine.  In either
invocation, the behavior of the code is driven by a config file.

The config file must be stored in an S3 bucket; it is always obtained
from here, even when running on a local (non-Lambda) system.  The
bucket name and the file/object name are contained in two environment
variables that must be set.  More about this below.

This configuration mechanism is a little clunky, but it does allow the
behavior to change without modifying code, repackaging, and
redeploying to Lambda.  I entertained the idea of providing all
configuration info via Lambda environment variables, but, due to the
amount of configurable info, I chose the S3 mechanism.

The config file contains YAML which, when loaded into a Python dict,
will look something like this:


    config = {

        'twilio': {
            'account_sid': 'YOUR ACCOUNT SID',
            'auth_token':  'YOUR AUTH TOKEN',
            'source_number': '+15125121234',
            }

        'notifier': {
            'person': {
                'address': 'YOUR STREET ADDRESS',
                'age': 'YOUR AGE',
                'name': 'YOUR NAME',
                'sex': 'YOUR SEX',
            },

            'sms_message': '{name} needs medical assistance. {address}.',
            'sms_numbers': [
                '+15125121235',
                '+15125121236',
            ]

            'voice_message': (
                '<Response><Say loop="5">This is an emergency. '
                'A {age} year old {sex}, {name}, needs medical assistance.'
                'The address {address}. </Say></Response>')
            'voice_numbers': [
                '+15125121237',
            ],
        },
    }

Two environment variables must be set to use this code, either on
Lambda or locally:

    BUCKET_NAME   - The name of the S3 bucket in which the
                    config file is stored.  Note that this
                    bucket must already exist -- you will
                    have to create it manually, but this is a
                    one-time event.

    KEY_NAME - The key_name (filename) used to store
               the config file in the bucket.

No validation is done on any of the input; it better be right or the
function will fail.

'''

from __future__ import print_function

import time
import os
import platform
import re
import StringIO
import sys
import yaml

from pprint import pprint as pp
from urllib import urlencode

import boto3

# NOTE that any packages used past this point MUST be
# included in the Lambda Distribution Package for this code.

from dotmap import DotMap
from twilio.rest import TwilioRestClient


def lambda_handler(event, context, aws_profile_name=None):
    '''This is the handler which is run by Lambda.

    Note that event and context are passed as args by Lambda.
    aws_profile_name will be None when this function is invoked by
    Lambda; it is only used when running locally.  aws_profile_name
    specifies the AWS profile to use when saving data to an S3 bucket.

    '''

    config = Config()
    config.load(aws_profile_name=aws_profile_name, filepath=None)
    notifier = Notifier(event, context, config)
    notifier.notify()

    return {'event': event}


class Config(object):
    '''Class to read, upload, download, and trivially validate config
    files and to store configuration information once read in.

    '''

    def __init__(self):

        try:
            self.config_bucket = os.environ.data['BUCKET_NAME']
            self.config_key_name = os.environ.data['KEY_NAME']
        except KeyError:
            msg = ('Error: Must set environment variables: '
                   'BUCKET_NAME and KEY_NAME')
            raise KeyError, msg
        return


    def get_s3client(self, aws_profile_name):
        '''Returns a boto S3 client object.

        '''

        if aws_profile_name:
            # non-Lambda invocation
            session = boto3.Session(profile_name=aws_profile_name)
            s3client = session.client('s3')
        else:
            # Lambda invocation
            s3client = boto3.client('s3')
        return s3client


    def _parse(self, stream):
        '''Parse the YAML from a config file, convert the dict into a
        DotMap object.

        '''

        return DotMap(yaml.load(stream))


    def upload(self, aws_profile_name, filepath):
        '''Upload a local file to S3.'''

        s3client = self.get_s3client(aws_profile_name)
        with open(filepath, 'rb') as f:
            s3client.upload_fileobj(f, self.config_bucket,
                                    self.config_key_name)
        return
    

    def get_content_stream(self, aws_profile_name, filepath):
        '''Get the content of the specified config file, which can be
        either local or stored on S3.  Returns a filelike object that
        can be read.

        If a filepath is provided, the contents of a local file are
        obtained. 
        
        If filepath is not provided, then the contents are obtained
        from S3. If aws_profile_name is provided, then it is assumed
        that this is running on a local system and that an AWS profile
        must be used to access S3.  If aws_profile_name is not
        provided, it is assumed that this is running under Lambda and
        that the Role assigned to the Lambda function will be used to
        access S3.

        In all cases, a stream is returned that, when read(), will
        provide the contents of the desired config file.

        '''

        if filepath:
            # Contents from local file
            stream = open(filepath, 'rb')
        else:
            # Contents from S3
            s3client = self.get_s3client(aws_profile_name)
            resp = s3client.get_object(Bucket=self.config_bucket,
                                       Key=self.config_key_name)
            stream = resp['Body']
        return stream


    def download(self, aws_profile_name, new_filepath):
        '''Download a S3 file and store in new_filepath.

        '''

        if os.path.exists(new_filepath):
            msg = 'Will not overwrite existing file: %s.' % new_filepath
            raise ValueError, msg
        stream = self.get_content_stream(aws_profile_name, None)
        with open(new_filepath, 'wb') as f:
            f.write(stream.read())
        return

    
    def load(self, aws_profile_name, filepath):
        '''Load the contents of a config file and return its resulting
        DotMap object.

        '''

        stream = self.get_content_stream(aws_profile_name, filepath)
        self.config = self._parse(stream)
        # Note that aws_profile_name is added to the config here
        self.config.notifier.aws_profile_name = aws_profile_name
        return self.config


class Notifier(object):
    '''Object to send voice and SMS messages via Twilo

    '''

    def __init__(self, event, context, config):
        '''Args:
              event (Lambda event) - 
                  Event passed by Lambda to the handler when triggered.
                  Currently unused.  Can be None.
              context (Lambda context) -
                  Context passed by Lambda to the handler when triggered.
                  Currently unused.  Can be None.
              config (Config) -
                  A Config object populated with the contents of the YAML
                  configuration file stored on S3.

        '''

        self.event = event
        self.context = context
        self.cfg = config.config

        self.client = TwilioRestClient(self.cfg.twilio.account_sid,
                                       self.cfg.twilio.auth_token)

        try:
            self.debug_bucket = self.cfg.notifier.debug_bucket
        except KeyError:
            self.debug_bucket = None


    def _clean_message(self, message):
        '''Returns new message, less unnecessary whitespace.

        Args:
            message (str) -
                String containing the voice/SMS message to be sent.

        '''
        message = re.sub(r' {2,}', ' ', message)
        message = re.sub(r'\n', ' ', message)
        message = message.strip()
        return message


    def notify(self):
        '''Perform the notifications specified in the config file.

        '''

        for number in self.cfg.notifier.voice_numbers:
            self.notify_voice(number)

        for number in self.cfg.notifier.sms_numbers:
            self.notify_sms(number)


    def notify_voice(self, number):
        '''Call the number, play the message via text-to-speech.

        Args:
            number (str) -
                String containing a single phone number to call.  Must
                be in Twilio acceptable format: '+1NNNEEEFFFF'.

        '''

        message = self._clean_message(
            self.cfg.notifier.voice_message.format(
                name=   self.cfg.notifier.person.name,
                age=    self.cfg.notifier.person.age,
                sex=    self.cfg.notifier.person.sex,
                address=self.cfg.notifier.person.address))
        query = {'Twiml': message}
        url = 'http://twimlets.com/echo?%s' % urlencode(query)
        call = self.client.calls.create(
            to=number,
            from_=self.cfg.twilio.source_number,
            url=url)


    def notify_sms(self, number):
        '''Send a SMS to the specified number.

        Args:
            number (str) -
                String containing a single phone number to call.  Must
                be in Twilio acceptable format: '+1NNNEEEFFFF'.

        '''
        
        fields = dict(name=self.cfg.notifier.person.name,
                      address=self.cfg.notifier.person.address,
                      clickType=self.event.get('clickType', None),
                      serialNumber=self.event.get('serialNumber', None),
                      batteryVoltage=self.event.get('batteryVoltage', None))
        message = self._clean_message(
            self.cfg.notifier.sms_message.format(**fields))
        sms = self.client.messages.create(
            body=message,
            to=number,
            from_=self.cfg.twilio.source_number
        )



if __name__ == '__main__':

    # On local system -- not on Lambda.

    from docopt import docopt
 

    usage = '''
    Usage:
        notifier sendmessages    --profile=PROFILE
        notifier config validate                   --path=CONFIGPATH
        notifier config upload   --profile=PROFILE --path=CONFIGPATH
        notifier config download --profile=PROFILE --path=CONFIGPATH

    Summary:
    When invoked from the commandline, this code is not running under
    Lambda.  Rather, it's likely running on a development system.  On
    a development system, notifier.py can be used to:

    sendmessages -
        Test sending the voice and SMS messages defined in the config
        file stored on S3.

    config validate -
        Confirm that the local config file specified by CONFIGPATH is
        valid YAML.  Note that syntax is validated but semantics are
        not. 

    config upload -
        Upload the config file stored locally at CONFIGPATH to S3.
        This will overwrite any existing config file on S3.  No
        validation is performed.  An AWS user profile must be
        specified in PROFILE.  This profile should be present in
        ~/.aws/credentials.  If you wish use another mechanism to
        provide credentials, you'll have to modify this code.  The
        credentials are used to obtain write permission to the S3
        bucket used to store the config file.

    config download -
        Download the current config file on S3 and store it in
        CONFIGPATH.  If a file exists at CONFIGPATH, it will not be
        overwritten.  PROFILE is as previously described.

    All of the code surrounding upload/download of the config file is
    probably overkill, but I hate using the Management Console.

    '''

    args = docopt(usage, version='notifier v1.0')
    args = {k.replace('-', '') : args[k] for k in args.keys()}
    args = DotMap(args)

    if args.validate:
        config = Config()
        config.load(aws_profile_name=None, filepath=args.path)
        pp(config.config)
        print('The configuration file is syntactically correct YAML.')
    elif args.upload:
        config = Config()
        config.upload(args.profile, args.path)
    elif args.download:
        config = Config()
        config.download(args.profile, args.path)
    elif args.sendmessages:
        # Simulate IoT Button event
        event = {
            "serialNumber": "DKJI89378KJLL",
            "clickType": "SINGLE",
            "batteryVoltage": "1975 mV"
        }
        lambda_handler(event=event, context=None,
                       aws_profile_name=args.profile)



#;;; Local Variables:
#;;; mode: python
#;;; coding: utf-8
#;;; eval: (auto-fill-mode)
#;;; eval: (set-fill-column 78)
#;;; eval: (fci-mode)
#;;; End:

#!/usr/bin/env python
# -*- coding: utf-8 -*-


'''
Usage:
    riprock [options] create-type
    riprock [options] create-policy
    riprock [options] create-button SERIALNUM
    riprock [options] create-certs SERIALNUM
    riprock [options] attach-principal-policy SERIALNUM
    riprock [options] attach-button-principal SERIALNUM
    riprock [options] one-shot SERIALNUM
    riprock [options] describe-endpoint
    riprock [options] click SERIALNUM (--single | --double | --long) [VOLTAGE]
    riprock [options] create-topic-rule SERIALNUM
    riprock [options] subscribe SERIALNUM

Options:
    --single         emulate single button press
    --multiple       emulate multiple button presses
    --certdir        pathname of directory in which to store certificates
    -h --help        show this help text
    --version        show
    --args           show commandline args then exit
    --config=CONFIG  path to configuration file to use

Description:
    riprock is example code showing how to provision an Amazon IoT Button
    within the Amazon IoT system.  It also offers the ability to simulate
    button clicks from an Amazon IoT Button.  This is probably not useful on a
    day-to-day or ongoing basis, but it should be helpful if you are just
    getting started with IoT Buttons and you'd like to see working code using
    Boto that fully provisions them.

    Note that riprock supports the use of a config file to control its
    behavior.  See the documentation for more info.  riprock assumes the
    following:
 
        1) You have an Amazon AWS account and you have created a user named
           'iotuser' that has admin access to the AWS IoT subsystem.
        2) You have a ~/.aws/credentials file with a section for the
           'iotuser'.  This section must contain the user's keys and the
           region to be used.

    If you are starting from scratch, with an empty IoT configuration, you
    will need to run a series of commands to completely provision IoT for the
    Button.  riprock is setup this way to illustrate everything that has to
    take place for a new Button to work properly.  There is also a single
    command that bundles all the required commands into a sigle invocation. 

    A set of certificates are created for each Button that is provisioned.  By
    default, these certificates are stored in ./certs.


Commands:
    get-rootca - Gets the root CA for Amazon IoT and stores in ./certs.

    create-type - Creates a Thing Type in the registry named 'iotbutton'.

    create-policy - Creates a security Policy named 'PubSubAll' that allows
        any action within IoT.
    
    create-button - Creates a Thing name 'iotbutton_' followed by the arg
        value SERIALNUM.  SERIALNUM must match your Button's serial number for
        things to work properly.  If you don't have a physical Button, you can
        make one up.

    create-certs - Creates the Certificates necessary for the Button to gain
        access to your IoT endpoint.  These are stored in ./certs.  Note that
        each button has its own set of Certificates.  SERIALNUM must match
        your Button's serial number. 

    attach-principal-policy - Attaches the previously created security Policy
        to the Certificates created by 'create-certs', thereby specifying the
        permissions granted to devices using the Certificates. SERIALNUM must
        match your Button's serial number.

    attach-button-principal - Attaches the previously created Certificates to
        the previously created Thing.  The Policy associated with the
        Certificates defines the permissions granted to the Thing. SERIALNUM
        must match your Button's serial number.

    one-shot - Runs 'create-button', 'create-certs',
        'attach-principal-policy', 'attach-thing-principal' in sequency for
        the provided SERIALNUM.  SERIALNUM must match your Button's serial
        number.  This is simply a convenience command.

ToDo:

    - It would probably be handy to have a 'delete-button' that removed
       everything associated with a button.

'''


import ConfigParser
import json
import logging
import os
import pdb
import re
import sys

from pprint import pprint as pp

import boto3
import requests

import subscriber
from common import docopt_plus
from iotbutton import AWSIoTButton

try:
    import debug  # uncaught exception starts pdb
except:
    pass


logger = None


def main(loglevel=logging.WARN):

    global logger

    logger = logging.getLogger(name='riprock')
    args = docopt_plus(__doc__, 'v 1.0')
    config = ConfigParser.SafeConfigParser()
    config.readfp(open('./riprock.conf'))

    if args.args:
        pp(args)
        sys.exit(0)

    certs_dir = os.path.expanduser(config.get('main', 'certs_dir'))
    root_ca_filename = config.get('main', 'root_ca')
    profile_name = config.get('main', 'aws_profile_name')

    iotb = AWSIoTButton(certs_dir, root_ca_filename, profile_name)

    resp = None
    if args.createtype:
        resp = iotb.create_thing_type()
    elif args.createpolicy:
        resp = iotb.create_policy()
    elif args.createbutton:
        resp = iotb.create_thing(args.SERIALNUM)
    elif args.createcerts:
        resp = iotb.create_keys_and_certificate(args.SERIALNUM)
    elif args.attachprincipalpolicy:
        resp = iotb.attach_principal_policy(args.SERIALNUM)
    elif args.attachbuttonprincipal:
        resp = iotb.attach_thing_principal(args.SERIALNUM)
    elif args.describeendpoint:
        endpoint = iotb.endpoint
        print 'AWS IoT endpoint = %s' % endpoint
    elif args.oneshot:
        resp = one_shot(args.SERIALNUM)
    elif args.click:
        click_type = 'SINGLE' if args.single else (
                     'DOUBLE' if args.double else (
                     'LONG'   if args.long   else None))
        voltage = args.VOLTAGE or '4321mV'
        iotb.click(args.SERIALNUM, click_type, voltage)
    elif args.createtopicrule:
        resp = iotb.create_topic_rule(args.SERIALNUM)
    elif args.subscribe:
        subscriber.subscribe_all(iotb, args.SERIALNUM)



    if resp: pp(resp)

    sys.exit(0)




if __name__ == '__main__':


    main(logging.WARN)



#;;; Local Variables:
#;;; mode: python
#;;; coding: utf-8
#;;; eval: (auto-fill-mode)
#;;; eval: (set-fill-column 78)
#;;; eval: (fci-mode)
#;;; End:

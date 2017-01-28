#!/usr/bin/env python

from __future__ import print_function

import datetime
import os
import socket
import ssl
import sys

import paho.mqtt.client as paho


def conout(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
    sys.stderr.flush()


def subscribe_all(iotb, serial_num):


    def on_connect(client, userdata, flags, rc):
        conout("Connection returned result: %s\n" % str(rc))
        # Subscribing in on_connect() means that if we lose the 
        # connection and reconnect then subscriptions will be renewed.
        client.subscribe("#" , 1 )


    def on_message(client, userdata, msg):
        conout(datetime.datetime.now().ctime())
        conout("topic: %s" % msg.topic)
        conout("payload: %s\n" % str(msg.payload))


    def on_log(client, userdata, level, msg):
        message = '%s %s\n' % (msg.topic, str(msg.payload))
        conout(message)

    # Must set serial_num so that paths will be correct
    iotb.set_serial_num(serial_num)

    mqttc = paho.Client(client_id="subscribeall")
    mqttc.on_connect = on_connect
    mqttc.on_message = on_message
    #mqttc.on_log = on_log

    awshost = iotb.endpoint
    awsport = 8883

    mqttc.tls_set(ca_certs=iotb.rootCA_pathname,
                  certfile=iotb.certificate,
                  keyfile=iotb.private_key,
                  cert_reqs=ssl.CERT_REQUIRED,
                  tls_version=ssl.PROTOCOL_TLSv1_2,
                  ciphers=None)

    mqttc.connect(awshost, awsport, keepalive=60)
    mqttc.loop_forever()

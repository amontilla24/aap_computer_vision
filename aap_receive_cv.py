#!/usr/bin/env python3
# encoding: utf-8

import argparse
import logging
import sys
import base64
import os

from google.cloud import vision
from ud3tn_utils.aap import AAPUnixClient, AAPTCPClient
from helpers import add_common_parser_arguments, logging_level


def run_aap_recv(aap_client, max_count=None, verify_pl=None, send_reply=False):

    print("Waiting for bundles...")

    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/home/ubuntu/Spatiam/ud3tn/spatiam-dtn-cloud-vision.json'

    client = vision.ImageAnnotatorClient()

    counter = 0
    while True:
        msg = aap_client.receive()
        if not msg:
            return

        b64bytes = msg.payload.decode('utf-8')

        msg_data = b64bytes.split('\n', 1)[0].split('#')
        filename = msg_data[0]
        msg_content = msg_data[1]

        b64bytes = b64bytes.split('\n', 1)[1]

        if msg_content == 'image':

            img_bytes = base64.b64decode(b64bytes)

            print("\nReceived '{}' from '{}'".format(
                filename, msg.eid,
            ))

            image = vision.Image(content=img_bytes)
            response = client.label_detection(image=image)
            labels = response.label_annotations
            x = len(labels)

            label_descriptions = []
            for label in labels:
                label_descriptions.append(str(label.description))
            label_desc_str = ', '.join(label_descriptions,)
            print("Identified '{}' Labels in the image: {}".format(x, label_desc_str))

            if send_reply:

                reply_msg = "{}#labels\n{}".format(filename, label_desc_str)

                scheme = msg.eid.split('//')[0]
                eid_name = msg.eid.split('//')[1].split('/', 1)[0]
                sink_eid = scheme + '//' + eid_name + '/sink_cv'

                print(
                    "Forwarding labels to '{}', see logs for more details".format(sink_eid))

                with AAPUnixClient(address=args.socket) as aap_client2:
                    aap_client2.register("source_label_cv")
                    aap_client2.send_str(sink_eid, reply_msg)

        else:
            print("\nReceived labels from '{}' of '{}':\n\t{}".format(
                msg.eid, filename, b64bytes,))

        counter += 1
        if max_count and counter >= max_count:
            print("\nExpected amount of bundles received, terminating.")
            return


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="register an agent with uD3TN and wait for bundles",
    )

    add_common_parser_arguments(parser)

    parser.add_argument(
        "-c", "--count",
        type=int,
        default=None,
        help="amount of bundles to be received before terminating",
    )
    parser.add_argument(
        "--verify-pl",
        default=None,
        help="verify that the payload is equal to the provided string",
    )
    parser.add_argument(
        "--send-reply",
        type=str2bool,
        nargs='?',
        const=True,
        default=False,
        help="Reply to the sender with image labels"
    )

    args = parser.parse_args()

    if args.verbosity:
        logging.basicConfig(level=logging_level(args.verbosity))

    if args.tcp:
        addr = (args.tcp[0], int(args.tcp[1]))
        with AAPTCPClient(address=addr) as aap_client:
            aap_client.register(args.agentid)
            run_aap_recv(aap_client, args.count,
                         args.verify_pl, args.send_reply)
    else:
        with AAPUnixClient(address=args.socket) as aap_client:
            aap_client.register(args.agentid)
            run_aap_recv(aap_client, args.count,
                         args.verify_pl, args.send_reply)
#!/bin/sh
""":" .

exec python "$0" "$@"
"""
# -*- coding: utf-8 -*-
"""
Copyright (c) 2018 beyond-blockchain.org.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import argparse
import binascii
import msgpack
import os
import json
import sys

from bbc1.core import bbc_app
from bbc1.core.bbc_config import DEFAULT_CORE_PORT
from bbc1.core import bbclib
from bbc1.core.message_key_types import KeyType
from bbc1.core.bbc_error import *


PRIVATE_KEY = ".private_key"
PUBLIC_KEY = ".public_key"

asset_group_id = bbclib.get_new_id("test_asset_group", include_timestamp=False)


def setup_bbc_client(domain_id, user_id):
    bbc_app_client = bbc_app.BBcAppClient(port=DEFAULT_CORE_PORT, multiq=False, loglevel="all")
    bbc_app_client.set_user_id(user_id)
    bbc_app_client.set_domain_id(domain_id)
    bbc_app_client.set_callback(bbc_app.Callback())
    ret = bbc_app_client.register_to_core()
    assert ret
    return bbc_app_client


def search_all_transactions_of_user(domain_id, user_id):
    """
    Search all transactions with the specified user's asset and return the list of the transactions
    :param domain_id:
    :param user_id:
    :return:
    """
    bbc_app_client = setup_bbc_client(domain_id, user_id)
    bbc_app_client.search_transaction_with_condition(asset_group_id=asset_group_id, user_id=user_id, direction=0, count=30)  # direction=0 means that the result is sorted in descending order in terms of timestamp (direction=1 means ascending)
    response_data = bbc_app_client.callback.synchronize()
    if response_data[KeyType.status] < ESUCCESS:
        print("ERROR: ", response_data[KeyType.reason].decode())
        return None

    txlist = list()
    for txdat in response_data[KeyType.transactions]:
        obj, fmt_type = bbclib.deserialize(txdat)
        txlist.append(obj)

    return txlist


def read_keypair_file():
    with open(PRIVATE_KEY, "rb") as fin:
        private_key = fin.read()
    with open(PUBLIC_KEY, "rb") as fin:
        public_key = fin.read()
    key_pair = bbclib.KeyPair(privkey=private_key, pubkey=public_key)
    return key_pair


def generate_transaction(user_id, previous_txid):
    """
    Generate a transaction object
    :param user_id:
    :param previous_txid:
    :return:
    """
    if previous_txid is not None:
        print(previous_txid.hex())

    # create a frame of transaction
    txobj = bbclib.make_transaction(relation_num=1, witness=True)

    # build asset body, which is the main data body you want to register in the bbc_core
    asset_body_dict = {
        "item_a": 1000,
        "item_b": "xxxx",
        "item_c": binascii.a2b_hex("0123456789")
    }
    asset_body_data = msgpack.dumps(asset_body_dict)  # in this example, messagepack is used to transform the body data into binary format

    # create relation object (BBcRelation) with asset and put the object into the transaction
    bbclib.add_relation_asset(txobj, relation_idx=0, asset_group_id=asset_group_id,
                              user_id=user_id, asset_body=asset_body_data)

    # if previous_txid is not None, set BBcPointer to the relation object
    if previous_txid is not None:
        bbclib.add_relation_pointer(txobj, 0, ref_transaction_id=previous_txid)

    # add witness to include signature of the user
    txobj.witness.add_witness(user_id)

    # sign to the transaction
    keypair = read_keypair_file()
    signature_obj = txobj.sign(private_key=keypair.private_key, public_key=keypair.public_key)
    txobj.witness.add_signature(user_id=user_id, signature=signature_obj)
    txobj.digest()
    return txobj


def register_transaction(domain_id, user_id, txobj):
    """
    Register the transaction to bbc_core
    :param domain_id: 
    :param user_id: 
    :param txobj: 
    :return: 
    """
    bbc_app_client = setup_bbc_client(domain_id, user_id)
    bbc_app_client.insert_transaction(txobj)
    response_data = bbc_app_client.callback.synchronize()
    if response_data[KeyType.status] < ESUCCESS:
        print("ERROR: ", response_data[KeyType.reason].decode())
        sys.exit(0)


def argument_parser():
    argparser = argparse.ArgumentParser(description='Generate a transaction and register it to bbc_core')
    argparser.add_argument('-i', '--id_file', action='store', default="ID_FILE", help='file including user_id of the user')
    return argparser.parse_args()


if __name__ == '__main__':
    parsed_args = argument_parser()
    if not os.path.exists(parsed_args.id_file):
        print("No id_file")
        sys.exit(1)

    # read domain_id config in the upper directory (filename is DOMAIN_ID)
    with open("../DOMAIN_ID", "r") as f:
        domain_id_str = f.readline()
    domain_id = binascii.a2b_hex(domain_id_str.rstrip())

    # set user_id from the user information file (JSON formatted)
    with open(parsed_args.id_file, "r") as f:
        user_info = json.load(f)
    user_id = binascii.a2b_hex(user_info["id"])

    # main part (search the previous transaction and create/register a new transaction)
    txobj_list = search_all_transactions_of_user(domain_id, user_id)
    if txobj_list is None or len(txobj_list) == 0:
        last_txid = None
    else:
        last_txid = txobj_list[0].transaction_id
    txobj = generate_transaction(user_id, last_txid)
    print("****** registered transaction is as follows:")
    print(txobj)
    register_transaction(domain_id, user_id, txobj)

#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

import json
import os
import pathlib

from eth_utils import remove_0x_prefix, add_0x_prefix
from ocean_utils.agreements.service_agreement import ServiceAgreement
from ocean_utils.agreements.service_types import ServiceTypes
from ocean_utils.aquarius.aquarius import Aquarius
from ocean_utils.ddo.ddo import DDO
from ocean_utils.did import DID, did_to_id

from brizo.constants import BaseURLs
from brizo.util import get_provider_account, keeper_instance, web3, get_config, generate_token, \
    do_secret_store_encrypt, do_secret_store_decrypt
from tests.conftest import get_publisher_account, get_consumer_account

PURCHASE_ENDPOINT = BaseURLs.BASE_BRIZO_URL + '/services/access/initialize'
SERVICE_ENDPOINT = BaseURLs.BASE_BRIZO_URL + '/services/consume'


def dummy_callback(*_):
    pass


def get_registered_ddo(account, providers=None):
    keeper = keeper_instance()
    aqua = Aquarius('http://localhost:5000')
    base = os.path.realpath(__file__).split(os.path.sep)[1:-1]
    path = pathlib.Path(os.path.join(os.path.sep, *base, 'ddo', 'ddo_sa_sample.json'))
    ddo = DDO(json_filename=path)
    ddo._did = DID.did()
    ddo_service_endpoint = aqua.get_service_endpoint(ddo.did)

    metadata = ddo.metadata
    metadata['base']['checksum'] = ddo.generate_checksum(ddo.did, metadata)
    checksum = metadata['base']['checksum']
    ddo.add_proof(checksum, account, keeper.sign_hash(checksum, account))

    encrypted_files = do_secret_store_encrypt(
        remove_0x_prefix(ddo.asset_id),
        json.dumps(metadata['base']['files']),
        account,
        get_config()
    )
    _files = metadata['base']['files']
    # only assign if the encryption worked
    if encrypted_files:
        index = 0
        for file in metadata['base']['files']:
            file['index'] = index
            index = index + 1
            del file['url']
        metadata['base']['encryptedFiles'] = encrypted_files

    keeper_instance().did_registry.register(
        ddo.asset_id,
        checksum=web3().sha3(text='new_asset'),
        url=ddo_service_endpoint,
        account=account,
        providers=providers
    )
    aqua.publish_asset_ddo(ddo)
    return ddo


def place_order(publisher_account, service_definition_id, ddo, consumer_account):
    keeper = keeper_instance()
    agreement_id = ServiceAgreement.create_new_agreement_id()
    agreement_template = keeper.escrow_access_secretstore_template
    publisher_address = publisher_account.address
    balance = keeper.token.get_token_balance(consumer_account.address)/(2**18)
    if balance < 20:
        keeper.dispenser.request_tokens(100, consumer_account)

    service_agreement = ServiceAgreement.from_ddo(service_definition_id, ddo)
    condition_ids = service_agreement.generate_agreement_condition_ids(
        agreement_id, ddo.asset_id, consumer_account.address, publisher_address, keeper)
    time_locks = service_agreement.conditions_timelocks
    time_outs = service_agreement.conditions_timeouts
    agreement_template.create_agreement(
        agreement_id,
        ddo.asset_id,
        condition_ids,

        time_locks,
        time_outs,
        consumer_account.address,
        consumer_account
    )

    return agreement_id


def lock_reward(agreement_id, service_agreement, consumer_account):
    keeper = keeper_instance()
    price = service_agreement.get_price()
    keeper.token.token_approve(keeper.lock_reward_condition.address, price, consumer_account)
    tx_hash = keeper.lock_reward_condition.fulfill(
        agreement_id, keeper.escrow_reward_condition.address, price, consumer_account)
    keeper.lock_reward_condition.get_tx_receipt(tx_hash)


def grant_access(agreement_id, ddo, consumer_account, publisher_account):
    keeper = keeper_instance()
    tx_hash = keeper.access_secret_store_condition.fulfill(
        agreement_id, ddo.asset_id, consumer_account.address, publisher_account
    )
    keeper.access_secret_store_condition.get_tx_receipt(tx_hash)


def test_consume(client):
    endpoint = BaseURLs.ASSETS_URL + '/consume'

    pub_acc = get_publisher_account()
    cons_acc = get_consumer_account()

    ddo = get_registered_ddo(pub_acc, providers=[pub_acc.address])
    service = ddo.get_service(service_type=ServiceTypes.ASSET_ACCESS)
    service_definition_id = service.service_definition_id

    # initialize an agreement
    agreement_id = place_order(pub_acc, service_definition_id, ddo, cons_acc)
    payload = dict({
        'serviceAgreementId': agreement_id,
        'consumerAddress': cons_acc.address
    })

    keeper = keeper_instance()
    signature = keeper.sign_hash(agreement_id, cons_acc)
    index = 0

    event = keeper.escrow_access_secretstore_template.subscribe_agreement_created(
        agreement_id, 15, None, (), wait=True
    )
    assert event, "Agreement event is not found, check the keeper node's logs"

    sa = ServiceAgreement.from_ddo(service_definition_id, ddo)
    lock_reward(agreement_id, sa, cons_acc)
    event = keeper.lock_reward_condition.subscribe_condition_fulfilled(
        agreement_id, 15, None, (), wait=True
    )
    assert event, "Lock reward condition fulfilled event is not found, check the keeper node's logs"

    grant_access(agreement_id, ddo, cons_acc, pub_acc)
    event = keeper.access_secret_store_condition.subscribe_condition_fulfilled(
        agreement_id, 15, None, (), wait=True
    )
    assert event or keeper.access_secret_store_condition.check_permissions(
            ddo.asset_id, cons_acc.address
    ), f'Failed to get access permission: agreement_id={agreement_id}, ' \
       f'did={ddo.did}, consumer={cons_acc.address}'

    # Consume using decrypted url
    files_list = json.loads(do_secret_store_decrypt(did_to_id(ddo.did), ddo.encrypted_files, pub_acc, get_config()))
    payload['url'] = files_list[index]['url']
    request_url = endpoint + '?' + '&'.join([f'{k}={v}' for k, v in payload.items()])

    response = client.get(
        request_url
    )
    assert response.status == '200 OK'

    # Consume using url index and signature (let brizo do the decryption)
    payload.pop('url')
    payload['signature'] = signature
    payload['index'] = index
    request_url = endpoint + '?' + '&'.join([f'{k}={v}' for k, v in payload.items()])
    response = client.get(
        request_url
    )
    assert response.status == '200 OK'


def test_empty_payload(client):
    consume = client.get(
        BaseURLs.ASSETS_URL + '/consume',
        data=None,
        content_type='application/json'
    )
    assert consume.status_code == 400

    publish = client.post(
        BaseURLs.ASSETS_URL + '/publish',
        data=None,
        content_type='application/json'
    )
    assert publish.status_code == 400


def test_publish(client):
    endpoint = BaseURLs.ASSETS_URL + '/publish'
    did = DID.did()
    asset_id = did_to_id(did)
    account = get_provider_account()
    test_urls = [
        'url 0',
        'url 1',
        'url 2'
    ]
    urls_json = json.dumps(test_urls)
    signature = keeper_instance().sign_hash(asset_id, account)
    address = web3().eth.account.recoverHash(asset_id, signature=signature)
    assert address.lower() == account.address.lower()

    payload = {
        'documentId': add_0x_prefix(asset_id),
        'signature': signature,
        'document': urls_json,
        'publisherAddress': account.address
    }
    post_response = client.post(
        endpoint,
        data=json.dumps(payload),
        content_type='application/json'
    )
    encrypted_url = post_response.data.decode('utf-8')
    assert encrypted_url.startswith('0x')

    # publish using auth token
    signature = generate_token(account)
    payload['signature'] = signature
    did = DID.did()
    asset_id = did_to_id(did)
    payload['documentId'] = add_0x_prefix(asset_id)
    post_response = client.post(
        endpoint,
        data=json.dumps(payload),
        content_type='application/json'
    )
    encrypted_url = post_response.data.decode('utf-8')
    assert encrypted_url.startswith('0x')

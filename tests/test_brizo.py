#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0
import json
import time

from squid_py.agreements.service_types import ServiceTypes
from squid_py.assets.asset import Asset
from squid_py.brizo.brizo import Brizo
from squid_py.ddo.metadata import Metadata
from squid_py.did import DID, did_to_id
from squid_py.keeper import Keeper
from squid_py.keeper.web3_provider import Web3Provider

from brizo.constants import BaseURLs
from brizo.util import get_provider_account, check_and_register_agreement_template

PURCHASE_ENDPOINT = BaseURLs.BASE_BRIZO_URL + '/services/access/initialize'
SERVICE_ENDPOINT = BaseURLs.BASE_BRIZO_URL + '/services/consume'


def dummy_callback(*_):
    pass


def get_registered_ddo(ocean_instance, account, providers=None):
    # ocean_instance.templates.create(ACCESS_SERVICE_TEMPLATE_ID, account)
    ddo = ocean_instance.assets.create(Metadata.get_example(), account, providers=providers)
    return Asset(dictionary=ddo.as_dictionary())


def test_consume(client, publisher_ocean_instance, consumer_ocean_instance):
    Brizo.set_http_client(client)
    endpoint = BaseURLs.ASSETS_URL + '/consume'

    pub_acc = publisher_ocean_instance.main_account
    cons_acc = consumer_ocean_instance.main_account

    asset = get_registered_ddo(publisher_ocean_instance, pub_acc, providers=[pub_acc.address])
    metadata = Metadata.get_example()
    files = metadata['base']['files']
    urls = [_file_dict['url'] for _file_dict in files]

    # initialize an agreement
    agreement_id = consumer_ocean_instance.assets.order(
        asset.did,
        'Access',
        cons_acc,
        auto_consume=False
    )
    payload = dict({
        'serviceAgreementId': agreement_id,
        'consumerAddress': cons_acc.address
    })

    signature = Keeper.get_instance().sign_hash(agreement_id, cons_acc)
    index = 2

    keeper = Keeper.get_instance()
    event = keeper.escrow_access_secretstore_template.subscribe_agreement_created(
        agreement_id, 15, None, (), wait=True
    )
    assert event, "Agreement event is not found, check the keeper node's logs"

    event = keeper.lock_reward_condition.subscribe_condition_fulfilled(
        agreement_id, 15, None, (), wait=True
    )
    assert event, "Lock reward condition fulfilled event is not found, check the keeper node's logs"

    event = keeper.access_secret_store_condition.subscribe_condition_fulfilled(
        agreement_id, 15, None, (), wait=True
    )
    assert event or consumer_ocean_instance.agreements.is_access_granted(
        agreement_id, asset.did, cons_acc.address
    ), f'Failed to get access permission: agreement_id={agreement_id}, ' \
        f'did={asset.did}, consumer={cons_acc.address}'

    event = keeper.escrow_reward_condition.subscribe_condition_fulfilled(
        agreement_id, 10, dummy_callback, (), wait=True)
    assert event, 'escrow reward not fulfilled.'

    # Consume using decrypted url
    payload['url'] = urls[index]
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


def test_handle_agreement_event(client, publisher_ocean_instance, consumer_ocean_instance):
    # create agreement by consumer
    pub_ocn, cons_ocn = publisher_ocean_instance, consumer_ocean_instance
    consumer_account = cons_ocn.main_account
    publisher_account = pub_ocn.main_account
    keeper = Keeper.get_instance()

    # Register asset
    ddo = get_registered_ddo(pub_ocn, publisher_account)

    service = ddo.get_service(service_type=ServiceTypes.ASSET_ACCESS)
    service_definition_id = service.service_definition_id

    agreement_id, signature = consumer_ocean_instance.agreements.prepare(
        ddo.did, service_definition_id, consumer_account
    )

    Brizo.set_http_client(client)
    # .create will register consumer to auto-handle events and fulfilling lock reward.
    cons_ocn.agreements.create(
        ddo.did,
        service_definition_id,
        agreement_id,
        signature,
        consumer_account.address,
        consumer_account
    )
    event = keeper.escrow_access_secretstore_template.subscribe_agreement_created(
        agreement_id, 15, dummy_callback, (), wait=True)
    event_agr_id = Web3Provider.get_web3().toHex(event.args["_agreementId"]) if event else None
    assert event and event_agr_id == agreement_id, f'Create agreement failed {event}'

    event = keeper.lock_reward_condition.subscribe_condition_fulfilled(
        agreement_id, 15, dummy_callback, (), wait=True)
    event_agr_id = Web3Provider.get_web3().toHex(event.args["_agreementId"]) if event else None
    assert event and event_agr_id == agreement_id, \
        f'lock reward maybe failed, no event: event={event}'

    # verify that publisher/provider is handling the new agreement and fulfilling the access condition
    event = keeper.access_secret_store_condition.subscribe_condition_fulfilled(
        agreement_id, 15, dummy_callback, (), wait=True)

    assert event or consumer_ocean_instance.agreements.is_access_granted(
        agreement_id, ddo.did, consumer_account.address
    ), f'Failed to get access permission: agreement_id={agreement_id}, ' \
        f'did={ddo.did}, consumer={consumer_account.address}'

    event = keeper.escrow_reward_condition.subscribe_condition_fulfilled(
        agreement_id, 15, dummy_callback, (), wait=True)
    assert event, 'escrow reward not fulfilled.'


def test_initialize_and_consume(client, publisher_ocean_instance, consumer_ocean_instance):
    print(publisher_ocean_instance.accounts)
    pub_ocn, cons_ocn = publisher_ocean_instance, consumer_ocean_instance
    consumer_account = cons_ocn.main_account
    publisher_account = pub_ocn.main_account

    check_and_register_agreement_template(
        publisher_ocean_instance, Keeper.get_instance(), publisher_ocean_instance.main_account)

    # Register asset
    ddo = get_registered_ddo(pub_ocn, publisher_account)

    service = ddo.get_service(service_type=ServiceTypes.ASSET_ACCESS)
    service_definition_id = service.service_definition_id

    agreement_id, signature = consumer_ocean_instance.agreements.prepare(
        ddo.did, service_definition_id, consumer_account
    )

    Brizo.set_http_client(client)

    cons_ocn.agreements.send(ddo.did, agreement_id, service_definition_id, signature,
                             consumer_account, auto_consume=True)
    # wait a bit until all service agreement events are processed
    i = 0
    while i < 30 and not consumer_ocean_instance.agreements.is_access_granted(
            agreement_id, ddo.did, consumer_account.address):
        time.sleep(1)
        i += 1

    assert cons_ocn.agreements.is_access_granted(
        agreement_id, ddo.did, consumer_account.address) is True, ''
    print('Service agreement executed and fulfilled, all good.')


def test_empty_payload(client, publisher_ocean_instance, consumer_ocean_instance):
    request_payload = None
    initialize = client.post(
        '/api/v1/brizo/services/access/initialize',
        data=request_payload,
        content_type='application/json'
    )
    assert initialize.status_code == 400


def test_publish(client, publisher_ocean_instance):
    ocn = publisher_ocean_instance
    endpoint = BaseURLs.ASSETS_URL + '/publish'
    did = DID.did()
    asset_id = did_to_id(did)
    account = get_provider_account(ocn)
    test_urls = [
        'url 0',
        'url 1',
        'url 2'
    ]
    urls_json = json.dumps(test_urls)
    signature = Keeper.get_instance().sign_hash(asset_id, account)
    address = Web3Provider.get_web3().personal.ecRecover(asset_id, signature)
    assert address.lower() == account.address.lower()

    payload = {
        'documentId': asset_id,
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
    did = DID.did()
    asset_id = did_to_id(did)
    signature = ocn.auth.store(account)
    payload = {
        'documentId': asset_id,
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

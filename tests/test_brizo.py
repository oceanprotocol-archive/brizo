#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0
import json
import time

from squid_py import ConfigProvider
from squid_py.agreements.register_service_agreement import register_service_agreement_consumer
from squid_py.agreements.service_agreement import ServiceAgreement
from squid_py.agreements.service_types import ServiceTypes
from squid_py.assets.asset import Asset
from squid_py.brizo.brizo import Brizo
from squid_py.ddo.metadata import Metadata
from squid_py.did import DID, did_to_id
from squid_py.keeper import Keeper
from squid_py.keeper.web3_provider import Web3Provider

from brizo.constants import BaseURLs
from brizo.util import get_provider_account
from tests.conftest import get_publisher_account, get_consumer_account

PURCHASE_ENDPOINT = BaseURLs.BASE_BRIZO_URL + '/services/access/initialize'
SERVICE_ENDPOINT = BaseURLs.BASE_BRIZO_URL + '/services/consume'


def get_registered_ddo(ocean_instance, account, providers=None):
    # ocean_instance.templates.create(ACCESS_SERVICE_TEMPLATE_ID, account)
    ddo = ocean_instance.assets.create(Metadata.get_example(), account, providers=providers)
    return Asset(dictionary=ddo.as_dictionary())


def get_events(event_filter, max_iterations=100, pause_duration=0.1):
    events = event_filter.get_new_entries()
    i = 0
    while not events and i < max_iterations:
        i += 1
        time.sleep(pause_duration)
        events = event_filter.get_new_entries()

    if not events:
        print('no events found in %s events filter.' % str(event_filter))
    return events


def process_enc_token(event):
    # should get accessId and encryptedAccessToken in the event
    print("token published event: %s" % event)


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
        'signedDocumentId': signature,
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


def test_consume(client, publisher_ocean_instance, consumer_ocean_instance):
    Brizo.set_http_client(client)
    endpoint = BaseURLs.ASSETS_URL + '/consume'

    pub_acc = get_publisher_account(ConfigProvider.get_config())
    cons_acc = get_consumer_account(ConfigProvider.get_config())

    asset = get_registered_ddo(publisher_ocean_instance, pub_acc, providers=[pub_acc.address])
    metadata = Metadata.get_example()
    files = metadata['base']['files']
    urls = [_file_dict['url'] for _file_dict in files]

    # This is a trick to give access to provider through the secretstore
    publisher_ocean_instance.assets.order(
        asset.did,
        'Access',
        pub_acc,
        auto_consume=False
    )

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

    # Consume using decrypted url
    payload['url'] = urls[index]
    request_url = endpoint + '?' + '&'.join([f'{k}={v}' for k, v in payload.items()])
    i = 0
    while i < 30 and not consumer_ocean_instance.agreements.is_access_granted(
            agreement_id, asset.did, cons_acc.address):
        time.sleep(1)
        i += 1

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


def test_initialize_and_consume(client, publisher_ocean_instance, consumer_ocean_instance):
    print(publisher_ocean_instance.accounts)
    pub_ocn, cons_ocn = publisher_ocean_instance, consumer_ocean_instance
    consumer_account = cons_ocn.main_account
    publisher_account = pub_ocn.main_account

    if publisher_ocean_instance._keeper.template_manager.get_num_templates() == 0:
        publisher_ocean_instance.templates.propose(
            publisher_ocean_instance._keeper.escrow_access_secretstore_template.address,
            publisher_ocean_instance.main_account)
        publisher_ocean_instance.templates.approve(
            publisher_ocean_instance._keeper.escrow_access_secretstore_template.address,
            publisher_ocean_instance.main_account)

    # Register asset
    ddo = get_registered_ddo(pub_ocn, publisher_account)

    print("did: %s" % ddo.did)

    service = ddo.get_service(service_type=ServiceTypes.ASSET_ACCESS)
    service_definition_id = service.service_definition_id

    agreement_id, signature = consumer_ocean_instance.agreements.prepare(
        ddo.did, service_definition_id, consumer_account
    )

    Brizo.set_http_client(client)
    # subscribe to events
    service_agreement = ServiceAgreement.from_ddo(service_definition_id, ddo)

    condition_ids = service_agreement.generate_agreement_condition_ids(
        agreement_id, ddo.asset_id, consumer_account.address, publisher_account.address,
        publisher_ocean_instance._keeper)

    register_service_agreement_consumer(
        publisher_ocean_instance._config.storage_path,
        publisher_account.address,
        agreement_id,
        ddo.did,
        service_agreement,
        service_definition_id,
        service_agreement.get_price(),
        ddo.encrypted_files,
        consumer_account,
        condition_ids,
        publisher_ocean_instance.agreements._asset_consumer.download,
    )

    cons_ocn.agreements.send(ddo.did, agreement_id, service_definition_id, signature,
                             consumer_account)
    # wait a bit until all service agreement events are processed
    time.sleep(15)
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

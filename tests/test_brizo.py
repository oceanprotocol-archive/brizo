#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

import json
import uuid

from eth_utils import add_0x_prefix, remove_0x_prefix
from ocean_utils.agreements.service_agreement import ServiceAgreement
from ocean_utils.agreements.service_factory import ServiceDescriptor, ServiceFactory
from ocean_utils.agreements.service_types import ServiceTypes
from ocean_utils.aquarius.aquarius import Aquarius
from ocean_utils.ddo.ddo import DDO
from ocean_utils.ddo.metadata import MetadataMain
from ocean_utils.ddo.public_key_rsa import PUBLIC_KEY_TYPE_RSA
from ocean_utils.did import DID, did_to_id, did_to_id_bytes
from ocean_utils.utils.utilities import checksum

from brizo.constants import BaseURLs
from brizo.util import (do_secret_store_decrypt, do_secret_store_encrypt, generate_token,
                        get_config,
                        get_provider_account, keeper_instance, web3)
from tests.conftest import get_consumer_account, get_publisher_account, get_sample_ddo

PURCHASE_ENDPOINT = BaseURLs.BASE_BRIZO_URL + '/services/access/initialize'
SERVICE_ENDPOINT = BaseURLs.BASE_BRIZO_URL + '/services/consume'


def dummy_callback(*_):
    pass


def get_registered_ddo(account, providers=None):
    keeper = keeper_instance()
    aqua = Aquarius('http://localhost:5000')
    metadata = get_sample_ddo()['service'][0]['attributes']
    metadata['main']['files'][0]['checksum'] = str(uuid.uuid4())

    ddo = DDO()
    ddo_service_endpoint = aqua.get_service_endpoint()

    metadata_service_desc = ServiceDescriptor.metadata_service_descriptor(metadata,
                                                                          ddo_service_endpoint)

    access_service_attributes = {"main": {
        "name": "dataAssetAccessServiceAgreement",
        "creator": account.address,
        "price": metadata[MetadataMain.KEY]['price'],
        "timeout": 3600,
        "datePublished": metadata[MetadataMain.KEY]['dateCreated']
    }}

    service_descriptors = [ServiceDescriptor.authorization_service_descriptor(
        'http://localhost:12001')]
    service_descriptors += [ServiceDescriptor.access_service_descriptor(
        access_service_attributes,
        'http://localhost:8030'
    )]

    service_descriptors = [metadata_service_desc] + service_descriptors

    services = ServiceFactory.build_services(service_descriptors)
    checksums = dict()
    for service in services:
        checksums[str(service.index)] = checksum(service.main)

    # Adding proof to the ddo.
    ddo.add_proof(checksums, account)

    did = ddo.assign_did(DID.did(ddo.proof['checksum']))

    access_service = ServiceFactory.complete_access_service(did,
                                                            'http://localhost:8030',
                                                            access_service_attributes,
                                                            keeper.escrow_access_secretstore_template.address,
                                                            keeper.escrow_reward_condition.address)
    for service in services:
        if service.type == 'access':
            ddo.add_service(access_service)
        else:
            ddo.add_service(service)

    ddo.proof['signatureValue'] = keeper.sign_hash(did_to_id_bytes(did), account)

    ddo.add_public_key(did, account.address)

    ddo.add_authentication(did, PUBLIC_KEY_TYPE_RSA)

    encrypted_files = do_secret_store_encrypt(
        remove_0x_prefix(ddo.asset_id),
        json.dumps(metadata['main']['files']),
        account,
        get_config()
    )
    _files = metadata['main']['files']
    # only assign if the encryption worked
    if encrypted_files:
        index = 0
        for file in metadata['main']['files']:
            file['index'] = index
            index = index + 1
            del file['url']
        metadata['encryptedFiles'] = encrypted_files

    keeper_instance().did_registry.register(
        ddo.asset_id,
        checksum=web3().toBytes(hexstr=ddo.asset_id),
        url=ddo_service_endpoint,
        account=account,
        providers=providers
    )
    aqua.publish_asset_ddo(ddo)
    return ddo


def place_order(publisher_account, ddo, consumer_account):
    keeper = keeper_instance()
    agreement_id = ServiceAgreement.create_new_agreement_id()
    agreement_template = keeper.escrow_access_secretstore_template
    publisher_address = publisher_account.address
    balance = keeper.token.get_token_balance(consumer_account.address) / (2 ** 18)
    if balance < 20:
        keeper.dispenser.request_tokens(100, consumer_account)

    service_agreement = ServiceAgreement.from_ddo(ServiceTypes.ASSET_ACCESS, ddo)
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

    # initialize an agreement
    agreement_id = place_order(pub_acc, ddo, cons_acc)
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

    sa = ServiceAgreement.from_ddo(ServiceTypes.ASSET_ACCESS, ddo)
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
    files_list = json.loads(
        do_secret_store_decrypt(did_to_id(ddo.did), ddo.encrypted_files, pub_acc, get_config()))
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
    did = DID.did({"0": str(uuid.uuid4())})
    asset_id = did_to_id(did)
    account = get_provider_account()
    test_urls = [
        'url 00',
        'url 11',
        'url 22'
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
    did = DID.did({"0": str(uuid.uuid4())})
    asset_id = did_to_id(did)
    payload['documentId'] = add_0x_prefix(asset_id)
    post_response = client.post(
        endpoint,
        data=json.dumps(payload),
        content_type='application/json'
    )
    encrypted_url = post_response.data.decode('utf-8')
    assert encrypted_url.startswith('0x')

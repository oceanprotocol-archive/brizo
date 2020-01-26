#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

import json
import uuid


from eth_utils import remove_0x_prefix


from brizo.util import do_secret_store_encrypt, get_config, web3, keeper_instance

from tests.conftest import get_sample_ddo, get_sample_ddo_with_compute_service,\
                           get_sample_algorithm_ddo

from plecos import plecos
from ocean_utils.ddo.ddo import DDO
from ocean_utils.utils.utilities import checksum
from ocean_utils.ddo.metadata import MetadataMain
from ocean_utils.aquarius.aquarius import Aquarius
from ocean_utils.did import DID, did_to_id_bytes
from ocean_utils.ddo.public_key_rsa import PUBLIC_KEY_TYPE_RSA
from ocean_utils.agreements.service_agreement import ServiceAgreement
from ocean_utils.agreements.service_factory import ServiceDescriptor, ServiceFactory
from ocean_utils.agreements.service_types import ServiceTypes


def get_access_service_descriptor(keeper, account, metadata):
    template_name = keeper.template_manager.SERVICE_TO_TEMPLATE_NAME[ServiceTypes.ASSET_ACCESS]
    access_service_attributes = {
        "main": {
            "name": "dataAssetAccessServiceAgreement",
            "creator": account.address,
            "price": metadata[MetadataMain.KEY]['price'],
            "timeout": 3600,
            "datePublished": metadata[MetadataMain.KEY]['dateCreated']
        }
    }

    return ServiceDescriptor.access_service_descriptor(
        access_service_attributes,
        'http://localhost:8030',
        keeper.template_manager.create_template_id(template_name)
    )


def get_compute_service_descriptor(keeper, account, price, metadata):
    template_name = keeper.template_manager.SERVICE_TO_TEMPLATE_NAME[ServiceTypes.CLOUD_COMPUTE]
    compute_service_attributes = {
        "main": {
            "name": "dataAssetComputeServiceAgreement",
            "creator": account.address,
            "price": price,
            "timeout": 3600,
            "datePublished": metadata[MetadataMain.KEY]['dateCreated']
        }
    }

    return ServiceDescriptor.compute_service_descriptor(
        compute_service_attributes,
        'http://localhost:8030/services/compute',
        keeper.template_manager.create_template_id(template_name)

    )


def get_dataset_ddo_with_access_service(account, providers=None):
    keeper = keeper_instance()
    metadata = get_sample_ddo()['service'][0]['attributes']
    metadata['main']['files'][0]['checksum'] = str(uuid.uuid4())
    service_descriptor = get_access_service_descriptor(keeper, account, metadata)
    return get_registered_ddo(account, metadata, service_descriptor, providers)

def get_registered_ddo(account, metadata, service_descriptor, providers=None):
    keeper = keeper_instance()
    aqua = Aquarius('http://localhost:5000')

    for did in aqua.list_assets():
        aqua.retire_asset_ddo(did)

    ddo = DDO()
    ddo_service_endpoint = aqua.get_service_endpoint()

    metadata_service_desc = ServiceDescriptor.metadata_service_descriptor(
        metadata, ddo_service_endpoint
    )
    service_descriptors = list([ServiceDescriptor.authorization_service_descriptor('http://localhost:12001')])
    service_descriptors.append(service_descriptor)

    service_descriptors = [metadata_service_desc] + service_descriptors

    services = ServiceFactory.build_services(service_descriptors)
    checksums = dict()
    for service in services:
        checksums[str(service.index)] = checksum(service.main)

    # Adding proof to the ddo.
    ddo.add_proof(checksums, account)

    did = ddo.assign_did(DID.did(ddo.proof['checksum']))

    stype_to_service = {s.type: s for s in services}
    access_service = stype_to_service[ServiceTypes.ASSET_ACCESS]

    name_to_address = {cname: cinst.address for cname, cinst in keeper.contract_name_to_instance.items()}
    access_service.init_conditions_values(did, contract_name_to_address=name_to_address)
    ddo.add_service(access_service)
    for service in services:
        ddo.add_service(service)

    ddo.proof['signatureValue'] = keeper.sign_hash(did_to_id_bytes(did), account)

    ddo.add_public_key(did, account.address)

    ddo.add_authentication(did, PUBLIC_KEY_TYPE_RSA)

    try:
        _oldddo = aqua.get_asset_ddo(ddo.did)
        if _oldddo:
            aqua.retire_asset_ddo(ddo.did)
    except ValueError:
        pass

    if not plecos.is_valid_dict_local(ddo.metadata):
        print(f'invalid metadata: {plecos.validate_dict_local(ddo.metadata)}')
        assert False, f'invalid metadata: {plecos.validate_dict_local(ddo.metadata)}'

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


def get_template_actor_types(keeper, template_id):
    actor_type_ids = keeper.template_manager.get_template(template_id).actor_type_ids
    return [keeper.template_manager.get_template_actor_type_value(_id) for _id in actor_type_ids]


def place_order(publisher_account, ddo, consumer_account, service_type):
    keeper = keeper_instance()
    agreement_id = ServiceAgreement.create_new_agreement_id()
    publisher_address = publisher_account.address
    # balance = keeper.token.get_token_balance(consumer_account.address)/(2**18)
    # if balance < 20:
    #     keeper.dispenser.request_tokens(100, consumer_account)

    service_agreement = ServiceAgreement.from_ddo(service_type, ddo)
    condition_ids = service_agreement.generate_agreement_condition_ids(
        agreement_id, ddo.asset_id, consumer_account.address, publisher_address, keeper)
    time_locks = service_agreement.conditions_timelocks
    time_outs = service_agreement.conditions_timeouts

    template_name = keeper.template_manager.SERVICE_TO_TEMPLATE_NAME[service_type]
    template_id = keeper.template_manager.create_template_id(template_name)
    actor_map = {'consumer': consumer_account.address, 'provider': publisher_address}
    actors = [actor_map[_type] for _type in get_template_actor_types(keeper, template_id)]

    keeper_instance().agreement_manager.create_agreement(
        agreement_id,
        ddo.asset_id,
        template_id,
        condition_ids,
        time_locks,
        time_outs,
        actors,
        consumer_account
    )

    return agreement_id


def get_algorithm_ddo(account, providers=None):
    keeper = keeper_instance()
    metadata = get_sample_algorithm_ddo()['service'][0]['attributes']
    metadata['main']['files'][0]['checksum'] = str(uuid.uuid4())
    service_descriptor = get_access_service_descriptor(keeper, account, metadata)
    return get_registered_ddo(account, metadata, service_descriptor, providers)

def get_dataset_ddo_with_compute_service(account, providers=None):
    keeper = keeper_instance()
    metadata = get_sample_ddo_with_compute_service()['service'][0]['attributes']
    metadata['main']['files'][0]['checksum'] = str(uuid.uuid4())
    service_descriptor = get_compute_service_descriptor(
        keeper, account, metadata[MetadataMain.KEY]['price'], metadata)
    return get_registered_ddo(account, metadata, service_descriptor, providers)

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
    
#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

import json
import time
import uuid


from eth_utils import remove_0x_prefix
from ocean_keeper.utils import get_account, add_ethereum_prefix_and_hash_msg
from ocean_utils.did_resolver.did_resolver import DIDResolver

from brizo.constants import BaseURLs
from brizo.util import do_secret_store_encrypt, get_config, web3, keeper_instance

from tests.conftest import get_sample_ddo, get_resource_path

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


def get_publisher_account():
    return get_account(0)


def get_consumer_account():
    return get_account(1)


def get_sample_algorithm_ddo():
    path = get_resource_path('ddo', 'ddo_sample_algorithm.json')
    assert path.exists(), f"{path} does not exist!"
    with open(path, 'r') as file_handle:
        metadata = file_handle.read()
    return json.loads(metadata)


def get_sample_ddo_with_compute_service():
    path = get_resource_path('ddo', 'ddo_with_compute_service.json')  # 'ddo_sa_sample.json')
    assert path.exists(), f"{path} does not exist!"
    with open(path, 'r') as file_handle:
        metadata = file_handle.read()
    return json.loads(metadata)


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
        f'http://localhost:8030{BaseURLs.ASSETS_URL}/consume',
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
        f'http://localhost:8030{BaseURLs.ASSETS_URL}/compute',
        keeper.template_manager.create_template_id(template_name)
    )


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


def get_dataset_ddo_with_access_service(account, providers=None):
    keeper = keeper_instance()
    metadata = get_sample_ddo()['service'][0]['attributes']
    metadata['main']['files'][0]['checksum'] = str(uuid.uuid4())
    service_descriptor = get_access_service_descriptor(keeper, account, metadata)
    return get_registered_ddo(account, metadata, service_descriptor, providers)


def get_registered_ddo(account, metadata, service_descriptor, providers=None):
    keeper = keeper_instance()
    aqua = Aquarius('http://localhost:5000')

    ddo = DDO()
    ddo_service_endpoint = aqua.get_service_endpoint()

    metadata_service_desc = ServiceDescriptor.metadata_service_descriptor(
        metadata, ddo_service_endpoint
    )
    service_descriptors = list([ServiceDescriptor.authorization_service_descriptor('http://localhost:12001')])
    service_descriptors.append(service_descriptor)
    service_type = service_descriptor[0]

    service_descriptors = [metadata_service_desc] + service_descriptors

    services = ServiceFactory.build_services(service_descriptors)
    checksums = dict()
    for service in services:
        checksums[str(service.index)] = checksum(service.main)

    # Adding proof to the ddo.
    ddo.add_proof(checksums, account)

    did = ddo.assign_did(DID.did(ddo.proof['checksum']))
    ddo_service_endpoint.replace('{did}', did)
    services[0].set_service_endpoint(ddo_service_endpoint)

    stype_to_service = {s.type: s for s in services}
    _service = stype_to_service[service_type]

    name_to_address = {cname: cinst.address for cname, cinst in keeper.contract_name_to_instance.items()}
    _service.init_conditions_values(did, contract_name_to_address=name_to_address)
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

    try:
        aqua.publish_asset_ddo(ddo)
    except Exception as e:
        print(f'error publishing ddo {ddo.did} in Aquarius: {e}')
        raise

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

    assert keeper.template_manager.contract_concise.isTemplateIdApproved(template_id), f'template {template_id} is not approved.'

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


def lock_reward(agreement_id, service_agreement, consumer_account):
    keeper = keeper_instance()
    price = service_agreement.get_price()
    keeper.token.token_approve(keeper.lock_reward_condition.address, price, consumer_account)
    time.sleep(3)
    tx_hash = keeper.lock_reward_condition.fulfill(
        agreement_id, keeper.escrow_reward_condition.address, price, consumer_account)
    keeper.lock_reward_condition.get_tx_receipt(tx_hash)


def grant_access(agreement_id, ddo, consumer_account, publisher_account):
    keeper = keeper_instance()
    tx_hash = keeper.access_secret_store_condition.fulfill(
        agreement_id, ddo.asset_id, consumer_account.address, publisher_account
    )
    keeper.access_secret_store_condition.get_tx_receipt(tx_hash)


def grant_compute(agreement_id, asset_id, consumer_account, publisher_account):
    keeper = keeper_instance()
    tx_hash = keeper.compute_execution_condition.fulfill(
        agreement_id, asset_id, consumer_account.address, publisher_account
    )
    keeper.compute_execution_condition.get_tx_receipt(tx_hash)


def get_possible_compute_job_status_text():
    return {
        10: 'Job started',
        20: 'Configuring volumes',
        30: 'Provisioning success',
        31: 'Data provisioning failed',
        32: 'Algorithm provisioning failed',
        40: 'Running algorithm',
        50: 'Filtering results',
        60: 'Publishing results',
        70: 'Job completed',
    }.values()


def get_compute_job_info(client, endpoint, params):
    response = client.get(
        endpoint + '?' + '&'.join([f'{k}={v}' for k, v in params.items()]),
        data=json.dumps(params),
        content_type='application/json'
    )
    assert response.status_code == 200 and response.data, \
        f'get compute job info failed: status {response.status}, data {response.data}'

    job_info = response.json if response.json else json.loads(response.data)
    if not job_info:
        print(f'There is a problem with the job info response: {response.data}')
        return None, None

    return job_info[0]


def _check_job_id(client, job_id, agreement_id, wait_time=20):
    endpoint = BaseURLs.ASSETS_URL + '/compute'
    cons_acc = get_consumer_account()

    keeper = keeper_instance()
    msg = f'{cons_acc.address}{job_id}{agreement_id}'
    agreement_id_hash = add_ethereum_prefix_and_hash_msg(msg)
    signature = keeper.sign_hash(agreement_id_hash, cons_acc)
    payload = dict({
        'signature': signature,
        'serviceAgreementId': agreement_id,
        'consumerAddress': cons_acc.address,
        'jobId': job_id,
    })

    job_info = get_compute_job_info(client, endpoint, payload)
    assert job_info, f'Failed to get job info for jobId {job_id}'
    print(f'got info for compute job {job_id}: {job_info}')
    assert job_info['statusText'] in get_possible_compute_job_status_text()
    did = None
    # get did of results
    for _ in range(wait_time*4):
        job_info = get_compute_job_info(client, endpoint, payload)
        did = job_info['did']
        if did:
            break
        time.sleep(0.25)

    assert did, f'Compute job has no results, job info {job_info}.'
    # check results ddo
    ddo = DIDResolver(keeper.did_registry).resolve(did)
    assert ddo, f'Failed to resolve ddo for did {did}'
    consumer_permission = keeper.did_registry.get_permission(did, cons_acc.address)
    assert consumer_permission is True, \
        f'Consumer address {cons_acc.address} has no permissions on the results ' \
        f'did {did}. This is required, the consumer must be able to access the results'

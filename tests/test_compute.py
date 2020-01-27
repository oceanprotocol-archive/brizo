#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

import json

from ocean_utils.agreements.service_agreement import ServiceAgreement
from ocean_utils.agreements.service_types import ServiceTypes

from brizo.constants import BaseURLs
from brizo.util import keeper_instance
from ocean_keeper.utils import add_ethereum_prefix_and_hash_msg

# TODO: move imports to `test_helpers.py`
from tests.test_helpers import (
    place_order,
    get_algorithm_ddo,
    get_dataset_ddo_with_compute_service,
    get_publisher_account,
    get_consumer_account,
    lock_reward, grant_compute)


def dummy_callback(*_):
    pass


def test_compute(client):

    endpoint = BaseURLs.ASSETS_URL + '/compute'
    pub_acc = get_publisher_account()
    cons_acc = get_consumer_account()

    keeper = keeper_instance()

    # publish a dataset asset
    dataset_ddo_w_compute_service = get_dataset_ddo_with_compute_service(pub_acc, providers=[pub_acc.address])

    # publish an algorithm asset (asset with metadata of type `algorithm`)
    alg_ddo = get_algorithm_ddo(cons_acc, providers=[pub_acc.address])
    # CHECKPOINT 1

    # prepare parameter values for the compute endpoint
    # signature, serviceAgreementId, consumerAddress, and algorithmDID or algorithmMeta

    # initialize an agreement
    agreement_id = place_order(pub_acc, dataset_ddo_w_compute_service, cons_acc, ServiceTypes.CLOUD_COMPUTE)
    # CHECKPOINT 2

    event = keeper.agreement_manager.subscribe_agreement_created(
        agreement_id, 15, None, (), wait=True, from_block=0
    )
    assert event, "Agreement event is not found, check the keeper node's logs"

    consumer_balance = keeper.token.get_token_balance(cons_acc.address)
    if consumer_balance < 50:
        keeper.dispenser.request_tokens(50-consumer_balance, cons_acc)

    sa = ServiceAgreement.from_ddo(ServiceTypes.CLOUD_COMPUTE, dataset_ddo_w_compute_service)
    lock_reward(agreement_id, sa, cons_acc)
    event = keeper.lock_reward_condition.subscribe_condition_fulfilled(
        agreement_id, 15, None, (), wait=True, from_block=0
    )
    assert event, "Lock reward condition fulfilled event is not found, check the keeper node's logs"

    grant_compute(agreement_id, dataset_ddo_w_compute_service.asset_id, cons_acc, pub_acc)
    event = keeper.compute_execution_condition.subscribe_condition_fulfilled(
        agreement_id, 15, None, (), wait=True, from_block=0
    )
    assert event or keeper.compute_execution_condition.was_compute_triggered(
        dataset_ddo_w_compute_service.asset_id, cons_acc.address
    ), f'Failed to compute: agreement_id={agreement_id}, ' \
       f'did={dataset_ddo_w_compute_service.did}, consumer={cons_acc.address}'

    # prepare consumer signature on agreement_id
    agreement_id_hash = add_ethereum_prefix_and_hash_msg(agreement_id)    
    signature = keeper.sign_hash(agreement_id_hash, cons_acc)

    payload = dict({
        'signature': signature, 
        'serviceAgreementId': agreement_id,
        'consumerAddress': cons_acc.address,
        'algorithmDID': alg_ddo.did,
        'algorithmMeta': {}
    })

    response = client.post(
        endpoint,
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert response.status == '200 OK', f'Failed: {response.content}'

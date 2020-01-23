#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

import json

from brizo.constants import BaseURLs
from brizo.util import keeper_instance
from ocean_keeper.utils import add_ethereum_prefix_and_hash_msg

from tests.test_brizo import (
    get_publisher_account,
    get_consumer_account,
    place_order,
    get_algorithm_ddo,
    get_dataset_ddo_with_compute_service,
)


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

    # prepare parameter values for the compute endpoint
    # signature, serviceAgreementId, consumerAddress, and algorithmDID or algorithmMeta

    # initialize an agreement
    # :TODO: place_order handles an agreement for a `access` service agreement,
    # but we need to order a service agreement for service type `compute`
    agreement_id = place_order(pub_acc, dataset_ddo_w_compute_service, cons_acc)

    # prepare consumer signature on agreement_id
    agreement_id_hash = add_ethereum_prefix_and_hash_msg(agreement_id)    
    signature = keeper.sign_hash(agreement_id_hash, cons_acc)

    payload = dict({
        'signature': signature, 
        'serviceAgreementId': agreement_id,
        'consumerAddress': cons_acc.address,
        'algorithmDID': alg_ddo.did
    })

    response = client.post(
        endpoint,
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert response.status == '200 OK'

#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

import json
import mimetypes
from unittest.mock import Mock, MagicMock
import uuid

from brizo.constants import BaseURLs
from brizo.util import keeper_instance
from ocean_utils.did import DID, did_to_id
from ocean_keeper.utils import add_ethereum_prefix_and_hash_msg

from tests.test_brizo import get_publisher_account, get_consumer_account, get_registered_ddo, place_order

# SERVICE_ENDPOINT = BaseURLs.BASE_BRIZO_URL + '/services/compute'

def dummy_callback(*_):
    pass

def test_compute(client):
    endpoint = BaseURLs.ASSETS_URL + '/compute'
    pub_acc = get_publisher_account()
    cons_acc = get_consumer_account()

    keeper = keeper_instance()

    ddo = get_registered_ddo(pub_acc, providers=[pub_acc.address])

    did = DID.did({"0": str(uuid.uuid4())})
    asset_id = did_to_id(did)
    asset_id_hash = add_ethereum_prefix_and_hash_msg(asset_id)    
    
    # initialize an agreement
    agreement_id = place_order(pub_acc, ddo, cons_acc)
    signature = keeper.sign_hash(agreement_id, cons_acc)
    
    payload = dict({
        'signature': signature, 
        'serviceAgreementId': agreement_id,
        'consumerAddress': cons_acc.address
    })

    request_url = endpoint + '?' + '&'.join([f'{k}={v}' for k, v in payload.items()])

    response = client.post(
        request_url
    )
    assert response.status == '200 OK'

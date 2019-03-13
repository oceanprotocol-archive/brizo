#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

import time

from squid_py.agreements.register_service_agreement import register_service_agreement_consumer
from squid_py.agreements.service_agreement import ServiceAgreement
from squid_py.agreements.service_types import ServiceTypes
from squid_py.assets.asset import Asset
from squid_py.brizo.brizo import Brizo
from squid_py.ddo.metadata import Metadata

from brizo.constants import BaseURLs

PURCHASE_ENDPOINT = BaseURLs.BASE_BRIZO_URL + '/services/access/initialize'
SERVICE_ENDPOINT = BaseURLs.BASE_BRIZO_URL + '/services/consume'


def get_registered_ddo(ocean_instance, account):
    # ocean_instance.templates.create(ACCESS_SERVICE_TEMPLATE_ID, account)
    ddo = ocean_instance.assets.create(Metadata.get_example(), account)
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

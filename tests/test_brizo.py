import os
import tempfile
import time

from squid_py.agreements.register_service_agreement import register_service_agreement
from squid_py.agreements.service_agreement import ServiceAgreement
from squid_py.agreements.service_agreement_template import ServiceAgreementTemplate
from squid_py.agreements.service_types import ACCESS_SERVICE_TEMPLATE_ID, ServiceTypes
from squid_py.agreements.utils import (
    get_sla_template_path,
    register_service_agreement_template
)
from squid_py.assets.asset import Asset
from squid_py.assets.asset_consumer import AssetConsumer
from squid_py.brizo.brizo import Brizo
from squid_py.ddo.metadata import Metadata

from brizo.constants import BaseURLs

PURCHASE_ENDPOINT = BaseURLs.BASE_BRIZO_URL + '/services/access/initialize'
SERVICE_ENDPOINT = BaseURLs.BASE_BRIZO_URL + '/services/consume'


def get_registered_access_service_template(ocean_instance, account):
    # register an asset Access service agreement template
    template = ServiceAgreementTemplate.from_json_file(get_sla_template_path())
    template_id = ACCESS_SERVICE_TEMPLATE_ID
    template_owner = ocean_instance.keeper.service_agreement.get_template_owner(template_id)
    if not template_owner:
        template = register_service_agreement_template(
            ocean_instance.keeper.service_agreement,
            account, template,
            ocean_instance.keeper.network_name
        )

    return template


def get_registered_ddo(ocean_instance, account):
    ocean_instance.templates.create(ACCESS_SERVICE_TEMPLATE_ID, account)
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

    # Register asset
    ddo = get_registered_ddo(pub_ocn, publisher_account)

    print("did: %s" % ddo.did)

    service = ddo.get_service(service_type=ServiceTypes.ASSET_ACCESS)
    service_definition_id = service.service_definition_id

    agreement_id, signature = consumer_ocean_instance.agreements.prepare(
        ddo.did, service_definition_id, consumer_account
    )

    service_agreement = ServiceAgreement.from_service_dict(service.as_dictionary())

    Brizo.set_http_client(client)
    # subscribe to events
    register_service_agreement(os.path.join(tempfile.gettempdir(), 'temp_squid_py.db'),
                               cons_ocn.main_account,
                               agreement_id,
                               ddo.did,
                               service.as_dictionary(),
                               'consumer',
                               service_definition_id,
                               service_agreement.get_price(),
                               ddo.encrypted_files,
                               AssetConsumer.download,
                               0)

    cons_ocn.agreements.send(ddo.did, agreement_id, service_definition_id, signature,
                             consumer_account)
    # wait a bit until all service agreement events are processed
    time.sleep(7)
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

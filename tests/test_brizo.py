import time

from squid_py.brizo.brizo_provider import BrizoProvider
from squid_py.ddo.metadata import Metadata
from squid_py.service_agreement.service_agreement import ServiceAgreement
from squid_py.service_agreement.register_service_agreement import register_service_agreement
from squid_py.service_agreement.service_agreement_template import ServiceAgreementTemplate
from squid_py.service_agreement.service_types import ServiceTypes
from squid_py.service_agreement.utils import get_sla_template_path, \
    register_service_agreement_template
from squid_py.utils.utilities import get_metadata_url
from squid_py import ACCESS_SERVICE_TEMPLATE_ID

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
    get_registered_access_service_template(ocean_instance, account)
    ddo = ocean_instance.register_asset(Metadata.get_example(), account)
    return ddo



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
    asset_price = 10

    # Register asset
    ddo = get_registered_ddo(pub_ocn, publisher_account)

    print("did: %s" % ddo.did)

    service_definition_id = \
        ddo.get_service(service_type=ServiceTypes.ASSET_ACCESS).get_values()[
            'serviceDefinitionId']

    agreement_id = ServiceAgreement.create_new_agreement_id()
    service_def = ddo.find_service_by_id(service_definition_id).as_dictionary()

    service_agreement = ServiceAgreement.from_ddo(service_definition_id, ddo)
    service_agreement.validate_conditions()
    agreement_hash = service_agreement.get_service_agreement_hash(agreement_id)
    cons_ocn.main_account.unlock()

    signature = consumer_account.sign_hash(agreement_hash)

    sa = service_agreement

    cons_ocn.main_account.unlock()
    cons_ocn._approve_token_transfer(service_agreement.get_price(), consumer_account)
    cons_ocn._http_client = client
    # subscribe to events
    register_service_agreement(cons_ocn.config.storage_path,
                               cons_ocn.main_account,
                               agreement_id,
                               ddo.did,
                               service_def,
                               'consumer',
                               service_definition_id,
                               service_agreement.get_price(),
                               get_metadata_url(ddo),
                               cons_ocn.consume_service,
                               0)

    request_payload = BrizoProvider.get_brizo().prepare_purchase_payload(ddo.did, agreement_id,
                                                                         service_definition_id,
                                                                         signature,
                                                                         consumer_account.address)
    initialize = client.post(
        sa.purchase_endpoint,
        data=request_payload,
        content_type='application/json'
    )
    print(initialize.status_code)
    assert initialize.status_code == 201
    assert pub_ocn.keeper.service_agreement.get_agreement_status(agreement_id) is False, ''
    # wait a bit until all service agreement events are processed
    time.sleep(15)
    assert pub_ocn.keeper.service_agreement.get_agreement_status(agreement_id) is True, ''
    print('Service agreement executed and fulfilled, all good.')
    # print('consumed : ', cons_ocn.get_consumed_results())


def test_empty_payload(client, publisher_ocean_instance, consumer_ocean_instance):
    request_payload = None
    initialize = client.post(
        '/api/v1/brizo/services/access/initialize',
        data=request_payload,
        content_type='application/json'
    )
    assert initialize.status_code == 400

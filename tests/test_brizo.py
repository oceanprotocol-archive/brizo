import os
import time

from squid_py.service_agreement.register_service_agreement import register_service_agreement
from squid_py.service_agreement.service_agreement_template import ServiceAgreementTemplate
from squid_py.service_agreement.utils import get_sla_template_path, register_service_agreement_template
from squid_py.utils.utilities import prepare_purchase_payload, get_metadata_url
from squid_py.ocean.asset import Asset
from squid_py.service_agreement.service_factory import ServiceDescriptor
from squid_py.service_agreement.service_types import ServiceTypes

from brizo.constants import BaseURLs

PURCHASE_ENDPOINT = BaseURLs.BASE_BRIZO_URL + '/services/access/initialize'
SERVICE_ENDPOINT = BaseURLs.BASE_BRIZO_URL + '/services/consume'


def get_registered_ddo(ocean_instance, price):
    # register an AssetAccess service agreement template
    sla_template = ServiceAgreementTemplate.from_json_file(get_sla_template_path())
    template_id = register_service_agreement_template(
        ocean_instance.keeper.service_agreement, ocean_instance.keeper.contract_path,
        ocean_instance.main_account, sla_template
    )
    assert template_id == sla_template.template_id

    service_descriptors = [ServiceDescriptor.access_service_descriptor(
        price, PURCHASE_ENDPOINT, SERVICE_ENDPOINT, 600, sla_template.template_id
    )]
    asset = Asset.from_ddo_json_file('./tests/json_sample.json')
    ddo = ocean_instance.register_asset(asset.metadata, ocean_instance.main_account.address, service_descriptors)

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
    print(publisher_ocean_instance._web3.eth.accounts)
    pub_ocn, cons_ocn = publisher_ocean_instance, consumer_ocean_instance
    web3 = pub_ocn.keeper.web3
    consumer_account = cons_ocn.main_account
    # publisher_account = pub_ocn.main_account
    asset_price = 10

    # Register asset
    asset_registered = get_registered_ddo(pub_ocn, asset_price)

    print("did: %s" % asset_registered.did)

    service_def_id = asset_registered.get_service(service_type=ServiceTypes.ASSET_ACCESS).get_values()['serviceDefinitionId']
    agreement_tuple = cons_ocn._get_service_agreement_to_sign(asset_registered.did, service_def_id)
    agreement_id, service_agreement, service_def, ddo = agreement_tuple
    sa = service_agreement

    cons_ocn.keeper.service_agreement.unlock_account(cons_ocn.main_account)
    signature = service_agreement.get_signed_agreement_hash(
        web3, cons_ocn.keeper.contract_path, agreement_id, consumer_account.address
    )[0]

    cons_ocn._approve_token_transfer(service_agreement.get_price())
    cons_ocn._http_client = client
    # subscribe to events
    register_service_agreement(web3, cons_ocn.keeper.contract_path, cons_ocn.config.storage_path, cons_ocn.main_account,
                               agreement_id, ddo.did, service_def, 'consumer', service_def_id,
                               service_agreement.get_price(), get_metadata_url(ddo), cons_ocn.consume_service, 0)

    request_payload = prepare_purchase_payload(ddo.did, agreement_id, service_def_id, signature, consumer_account.address)
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

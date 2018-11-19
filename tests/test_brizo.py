import json
import time

from brizo.constants import BaseURLs
from eth_account.messages import defunct_hash_message
from squid_py.ocean.asset import Asset
from squid_py.ocean.ocean import Ocean
from squid_py.service_agreement.service_factory import ServiceDescriptor
from squid_py.utils.utilities import watch_event
from squid_py.service_agreement.service_types import ServiceTypes
from squid_py.service_agreement.service_agreement import ServiceAgreement

ocean = Ocean(config_file='config_local.ini')

acl_concise = ocean.keeper.auth.contract_concise
acl = ocean.keeper.auth.contract
market_concise = ocean.keeper.market.contract_concise
market = ocean.keeper.market.contract
token = ocean.keeper.token.contract_concise


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


def test_brizo(client):
    expire_seconds = 9999999999
    consumer_account = ocean._web3.eth.accounts[1]
    publisher_address = ocean._web3.eth.accounts[0]
    asset_price = 10
    # Register asset
    service_descriptors = [
        ServiceDescriptor.access_service_descriptor(asset_price, '/purchaseEndpoint', '/serviceEndpoint', 600)]
    asset = Asset.from_ddo_json_file('./tests/json_sample.json')
    # ddo = ocean.register_asset(asset.metadata, publisher_address, service_descriptors)
    #
    # print("did: %s" % asset.did)
    #
    # market_concise.requestTokens(2000, transact={'from': consumer_account})
    #
    # json_request_initialize = dict()
    # json_request_initialize['consumerAddress'] = consumer_account
    # json_request_initialize['did'] = asset.did
    # json_request_initialize['serviceAgreementId'] =ddo.get_service(service_type=ServiceTypes.ASSET_ACCESS)._values['slaTemplateId']
    # json_request_initialize['serviceDefinitionId'] = ddo.get_service(service_type=ServiceTypes.ASSET_ACCESS)._values['serviceDefinitionId']
    # # json_request_initialize['signature'] = ''  # sa.get_signed_agreement_hash(self._web3, did_to_id(did), service_agreement_id, consumer)[0]
    # intialize = client.post(BaseURLs.BASE_BRIZO_URL,
    #                         data=json.dumps(json_request_initialize),
    #                         content_type='application/json')


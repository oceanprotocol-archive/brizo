import json
import time

from aquarius.constants import BaseURLs
from eth_account.messages import defunct_hash_message
from squid_py.acl import generate_encryption_keys, decode, decrypt
from squid_py.asset import Asset
from squid_py.ocean import Ocean
from squid_py.utils.utilities import watch_event

from tests.conftest import json_dict, json_request_consume

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


def test_commit_access_requested(client):
    expire_seconds = 9999999999
    consumer_account = ocean._web3.eth.accounts[1]
    aquarius_account = ocean._web3.eth.accounts[0]
    print("Starting test_commit_access_requested")
    print("buyer: %s" % consumer_account)
    print("seller: %s" % aquarius_account)

    asset_id = market_concise.generateId('resource', transact={'from': aquarius_account})
    print("recource_id: %s" % asset_id)
    resource_price = 10
    json_dict['id'] = ocean._web3.toHex(asset_id)
    asset = Asset(asset_id, None, resource_price, json_dict)
    ocean.metadata.publish_asset_metadata(asset)

    pubprivkey = generate_encryption_keys()
    pubkey = pubprivkey.public_key
    privkey = pubprivkey.private_key

    market_concise.requestTokens(2000, transact={'from': aquarius_account})
    market_concise.requestTokens(2000, transact={'from': consumer_account})

    # 1. Aquarius register an asset
    market_concise.register(asset_id,
                            resource_price,
                            transact={'from': aquarius_account})
    # 2. Consumer initiate an access request
    expiry = int(time.time() + expire_seconds)
    req = acl_concise.initiateAccessRequest(asset_id,
                                            aquarius_account,
                                            pubkey,
                                            expiry,
                                            transact={'from': consumer_account})
    ocean.keeper.web3.eth.waitForTransactionReceipt(req)
    receipt = ocean.keeper.web3.eth.getTransactionReceipt(req)
    send_event = acl.events.AccessConsentRequested().processReceipt(receipt)
    request_id = send_event[0]['args']['_id']

    # events = get_events(filter_access_consent)

    # assert send_event[0] in events
    assert acl_concise.statusOfAccessRequest(request_id) == 0 or acl_concise.statusOfAccessRequest(request_id) == 1

    filter_token_published = watch_event(acl, 'EncryptedTokenPublished', process_enc_token, 0.25,
                                                   fromBlock='latest')  # , filters={"id": request_id})

    # 3. Aquarius commit the request in commit_access_request

    # Verify consent has been emited
    i = 0
    while (acl_concise.statusOfAccessRequest(request_id) == 1) is False and i < 100:
        i += 1
        time.sleep(0.1)

    assert acl_concise.statusOfAccessRequest(request_id) == 1

    # 4. consumer make payment after approve spend token
    token.approve(ocean._web3.toChecksumAddress(market_concise.address),
                  resource_price,
                  transact={'from': consumer_account})

    buyer_balance_start = token.balanceOf(consumer_account)
    seller_balance_start = token.balanceOf(aquarius_account)
    print('starting buyer balance = ', buyer_balance_start)
    print('starting seller balance = ', seller_balance_start)

    market_concise.sendPayment(request_id,
                               aquarius_account,
                               resource_price,
                               expiry,
                               transact={'from': consumer_account, 'gas': 400000})

    print('buyer balance = ', token.balanceOf(consumer_account))
    print('seller balance = ', token.balanceOf(aquarius_account))

    events = get_events(filter_token_published)
    assert events
    assert events[0].args['_id'] == request_id
    on_chain_enc_token = events[0].args["_encryptedAccessToken"]
    # on_chain_enc_token2 = acl_concise.getEncryptedAccessToken(request_id, call={'from': consumer_account})

    decrypted_token = decrypt(on_chain_enc_token, privkey)
    # pub_key = ocean.encoding_key_pair.public_key
    access_token = decode(decrypted_token)

    assert pubkey == access_token['temp_pubkey']
    signature = ocean._web3.eth.sign(consumer_account, data=on_chain_enc_token)

    fixed_msg = defunct_hash_message(hexstr=ocean._web3.toHex(on_chain_enc_token))

    # helper.split_signature(signature)
    json_request_consume['fixed_msg'] = ocean._web3.toHex(fixed_msg)
    json_request_consume['consumerId'] = consumer_account
    json_request_consume['sigEncJWT'] = ocean._web3.toHex(signature)
    json_request_consume['jwt'] = ocean._web3.toBytes(hexstr=ocean._web3.toHex(decrypted_token)).decode('utf-8')

    post = client.post(
        access_token['service_endpoint'].split('8030')[1] + '/%s' % ocean._web3.toHex(asset_id),
        data=json.dumps(json_request_consume),
        content_type='application/json')
    print(post.data.decode('utf-8'))
    assert post.status_code == 200
    while (acl_concise.statusOfAccessRequest(request_id) == 3) is False and i < 1000:
        i += 1
        time.sleep(0.1)
    assert acl_concise.statusOfAccessRequest(request_id) == 3

    buyer_balance = token.balanceOf(consumer_account)
    seller_balance = token.balanceOf(aquarius_account)
    print('end: buyer balance -- current %s, starting %s, diff %s' % (
        buyer_balance, buyer_balance_start, (buyer_balance - buyer_balance_start)))
    print('end: seller balance -- current %s, starting %s, diff %s' % (
        seller_balance, seller_balance_start, (seller_balance - seller_balance_start)))
    assert token.balanceOf(consumer_account) == buyer_balance_start - resource_price
    assert token.balanceOf(aquarius_account) == seller_balance_start + resource_price
    client.delete(
        BaseURLs.BASE_AQUARIUS_URL + '/assets/ddo/%s' % ocean._web3.toHex(asset_id)
    )
    print('All good \/')

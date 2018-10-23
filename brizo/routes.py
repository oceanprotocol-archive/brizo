import logging

from flask import Blueprint, jsonify, request, redirect
from squid_py.acl import decode
from squid_py.config import Config
from squid_py.ocean import Ocean

from brizo.constants import BaseURLs
from brizo.constants import ConfigSections
from brizo.filters import Filters
from brizo.log import setup_logging
from brizo.myapp import app
from brizo.osmosis import Osmosis

setup_logging()
services = Blueprint('services', __name__)

config_file = app.config['CONFIG_FILE']
config = Config(filename=config_file)
# Prepare keeper contracts for on-chain access control
# Prepare OceanDB
brizo_url = config.get(ConfigSections.RESOURCES, 'brizo.url')
brizo_url += BaseURLs.ASSETS_URL

provider_address = None if not config.get(ConfigSections.KEEPER_CONTRACTS, 'provider.address') else config.get(
    ConfigSections.KEEPER_CONTRACTS,
    'provider.address')
ocn = Ocean(config_file=config_file)


def get_provider_address_filter():
    account = ocn.web3.eth.accounts[0] if not config.get(ConfigSections.KEEPER_CONTRACTS, 'provider.address') \
        else config.get(ConfigSections.KEEPER_CONTRACTS, 'provider.address')
    return {"address": account}


filters = Filters(squid=ocn, api_url=brizo_url)
filter_access_consent = ocn.helper.watch_event(ocn.contracts.auth.contract,
                                               'AccessConsentRequested',
                                               filters.commit_access_request,
                                               0.2,
                                               fromBlock='latest',
                                               filters=get_provider_address_filter())

filter_payment = ocn.helper.watch_event(ocn.contracts.market.contract,
                                        'PaymentReceived',
                                        filters.publish_encrypted_token,
                                        0.2,
                                        fromBlock='latest',
                                        filters=get_provider_address_filter())


@services.route('/consume/<asset_id>', methods=['POST'])
def consume_resource(asset_id):
    """Allows download of asset data file from this provider.

    Data file can be stored locally at the provider end or at some cloud storage.
    It is assumed that the asset is already purchased by the consumer (even for
    free/commons assets, the consumer must still go through the purchase contract
    transaction).

    ---
    tags:
      - services

    consumes:
      - application/json
    parameters:
      - name: asset_id
        in: path
        description: ID of the asset.
        required: true
        type: string
      - in: body
        name: body
        required: true
        description: Asset metadata.
        schema:
          type: object
          required:
            - consumerId
            - fixed_msg
            - sigEncJWT
            - jwt
          properties:
            consumerId:
              description:
              type: string
              example: '0x0234242345'
            fixed_msg:
              description:
              type: string
              example: 'fixedmsg'
            sigEncJWT:
              description:
              type: string
              example: '34tgsdfgv43hr34psdf5bvtqcw45'
            jwt:
              description:
              type: string
              example: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'

    """
    # Get asset metadata record
    required_attributes = ['consumerId', 'fixed_msg', 'sigEncJWT', 'jwt']
    assert isinstance(request.json, dict), 'invalid payload format.'
    logging.info('got "consume" request: %s' % request.json)
    data = request.json
    if not data:
        logging.error('Consume failed: data is empty.')
        return 'payload seems empty.', 400

    assert isinstance(data, dict), 'invalid `body` type, should already formatted into a dict.'

    for attr in required_attributes:
        if attr not in data:
            logging.error('Consume failed: required attr %s missing.' % attr)
            return '"%s" is required for registering an asset.' % attr, 400

    contract_instance = ocn.contracts.auth.contract_concise
    sig = ocn.helper.split_signature(ocn.web3.toBytes(hexstr=data['sigEncJWT']))
    jwt = decode(data['jwt'])

    if contract_instance.verifyAccessTokenDelivery(jwt['request_id'],  # requestId
                                                   ocn.web3.toChecksumAddress(data['consumerId']),
                                                   # consumerId
                                                   data['fixed_msg'],
                                                   sig.v,  # sig.v
                                                   sig.r,  # sig.r
                                                   sig.s,  # sig.s
                                                   transact={'from': ocn.web3.eth.accounts[0] if config.get(
                                                       ConfigSections.KEEPER_CONTRACTS,
                                                       'provider.account') is '' else config.get(
                                                       ConfigSections.KEEPER_CONTRACTS, 'provider.account'),
                                                             'gas': 4000000}):
        if jwt['resource_server_plugin'] == 'Azure':
            logging.info('reading asset from oceandb: %s' % asset_id)
            urls = ocn.metadata.get_asset_metadata(asset_id)['base']['contentUrls']
            # urls = dao.get(asset_id)['base']['contentUrls']
            url_list = []
            for url in urls:
                url_list.append(
                    Osmosis.generate_sasurl(url, config.get(ConfigSections.RESOURCES, 'azure.account.name'),
                                            config.get(ConfigSections.RESOURCES, 'azure.account.key'),
                                            config.get(ConfigSections.RESOURCES, 'azure.container')))
            return jsonify(url_list), 200
        else:
            logging.error('resource server plugin is not supported: %s' % jwt['resource_server_plugin'])
            return '"%s error generating the sasurl.' % asset_id, 404
    else:
        return '"%s error generating the sasurl.' % asset_id, 404


@services.route('/exec', methods=['POST'])
def exec():
    """Allows to execute an algorithm inside in a docker instance in the cloud provider.


    If the publisher of the assets
    provide this service in the Service agreement related with the asset_did requested.

    ---
    tags:
      - services

    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        description: Asset metadata.
        schema:
          type: object
          required:
            - asset_did
            - algorithm_did
            - consumer_wallet
          properties:
            asset_did:
              description: Identifier of the asset registered in ocean
              type: string
              example: '0x0234242345'
            algorithm_did:
              description: Identifier of the algorithm to execute
              type: string
              example: '0x0234242345'
            consumer_wallet:
              description: Address of the wallet of the consumer of the asset. Ex. data-science...
              type: string
              example: '0x0234242345'
            docker_image:
              description: Docker image where the algorithm is going to be executed. It must include all the libraries needs to run it.
              type: string
              example: python:3.6-alpine
            memory:
              description: Ammout of memory in Gb to run the algorithm
              type: number
              example: 1.5
            cpu:
              description: Number of cpus to execute the algorithm.
              type: integer
              example: 1
    """
    required_attributes = ['asset_did', 'algorithm_did', 'consumer_wallet']
    assert isinstance(request.json, dict), 'invalid payload format.'
    logging.info('got "exec" request: %s' % request.json)
    data = request.json
    if not data:
        logging.error('Consume failed: data is empty.')
        return 'payload seems empty.', 400

    assert isinstance(data, dict), 'invalid `body` type, should already formatted into a dict.'

    for attr in required_attributes:
        if attr not in data:
            logging.error('Consume failed: required attr %s missing.' % attr)
            return '"%s" is required for registering an asset.' % attr, 400

    osm = Osmosis()
    return osm.exec_container(asset_url=data.get('asset_did'),
                              algorithm_url=data.get('algorithm_did'),
                              resource_group_name=config.get(ConfigSections.RESOURCES, 'azure.resource_group'),
                              account_name=config.get(ConfigSections.RESOURCES, 'azure.account.name'),
                              account_key=config.get(ConfigSections.RESOURCES, 'azure.account.key'),
                              share_name_input=config.get(ConfigSections.RESOURCES, 'azure.share.input'),
                              share_name_output=config.get(ConfigSections.RESOURCES, 'azure.share.output'),
                              location=config.get(ConfigSections.RESOURCES, 'azure.location'),
                              # input_mount_point=data.get('input_mount_point'),
                              # output_mount_point=data.get('output_mount_point'),
                              docker_image=data.get('docker_image'),
                              memory=data.get('memory'),
                              cpu=data.get('cpu')), 200

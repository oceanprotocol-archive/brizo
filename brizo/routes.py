import logging
from flask import Blueprint, jsonify, request
from squid_py.config import Config
from squid_py.ocean.ocean import Ocean
from squid_py.utils.utilities import watch_event, split_signature
from brizo.constants import BaseURLs
from brizo.constants import ConfigSections
from brizo.log import setup_logging
from brizo.myapp import app
from osmosis_driver_interface.osmosis import Osmosis

setup_logging()
services = Blueprint('services', __name__)

config_file = app.config['CONFIG_FILE']
config = Config(filename=config_file)
# Prepare keeper contracts for on-chain access control
# Prepare OceanDB
brizo_url = config.get(ConfigSections.RESOURCES, 'brizo.url')
brizo_url += BaseURLs.ASSETS_URL

# aquarius_address = None if not config.get(ConfigSections.KEEPER_CONTRACTS, 'aquarius.address') else config.get(
#     ConfigSections.KEEPER_CONTRACTS,
#     'aquarius.address')
ocn = Ocean(config_file=config_file)


# def get_aquarius_address_filter():
#     account = ocn._web3.eth.accounts[0] if not config.get(ConfigSections.KEEPER_CONTRACTS, 'aquarius.address') \
#         else config.get(ConfigSections.KEEPER_CONTRACTS, 'aquarius.address')
#     return {"address": account}

#
# filters = Filters(squid=ocn, api_url=brizo_url)
# filter_access_consent = watch_event(ocn.keeper.auth.contract,
#                                     'AccessConsentRequested',
#                                     filters.commit_access_request,
#                                     0.2,
#                                     fromBlock='latest',
#                                     filters=get_aquarius_address_filter())
#
# filter_payment = watch_event(ocn.keeper.market.contract,
#                              'PaymentReceived',
#                              filters.publish_encrypted_token,
#                              0.2,
#                              fromBlock='latest',
#                              filters=get_aquarius_address_filter())
#
# # filter_locked_payment = watch_event(ocn.keeper.service_agreement.contract,
# #                                     'PaymentLocked',
# #                                     filters.grant_access,
# #                                     0.2,
# #                                     fromBlock='latest',
# #                                     filters={"serviceAgreementId": said})

# TODO run in cases of brizo crash or you restart
ocn.execute_pending_service_agreements()

@services.route('/access/initialize', methods=['POST'])
def initialize():
    """Initialize the SLA between the puvblisher and the consumer.

    ---
    tags:
      - services
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        description: Service agreement initialization.
        schema:
          type: object
          required:
            - did
            - serviceAgreementId
            - serviceDefinitionId
            - signature
            - consumerPublicKey:
          properties:
            did:
              description: Identifier of the asset registered in ocean.
              type: string
              example: 'did:op:08a429b8529856d59867503f8056903a680935a76950bb9649785cc97869a43d'
            serviceAgreementId:
              description: Identifier of the service agreement.
              type: string
              example: 'bb23s87856d59867503f80a690357406857698570b964ac8dcc9d86da4ada010'
            serviceDefinitionId:
              description: Identifier of the service definition.
              type: string
              example: '0'
            signature:
              description: Signature
              type: string
              example: 'cade376598342cdae231321a0097876aeda656a567a67c6767fd8710129a9dc1'
            consumerPublicKey:
              description: Consumer public key.
              type: string
              example: '0x00a329c0648769A73afAc7F9381E08FB43dBEA72'
    responses:
      201:
        description: Service agreement initialize successfully.
      400:
        description: One of the required attributes is missed.
      404:
        description: Invalid asset data.
      500:
        description: Error
    """
    required_attributes = ['did', 'serviceAgreementId', 'serviceDefinitionId', 'signature', 'consumerPublicKey']
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

    # Check signature
    try:
        if ocn.check_signature(data.get('signature')):
            # TODO Retrieve the ddo an update the serviceAgreementId.
            ocn.metadata.get_asset_metadata(data.get('did'))
            ocn.execute_service_agreement(sa_id=data.get('serviceAgreementId'),
                                          signature=data.get('signature'),
                                          sa_message_hash=,
                                          consumer_address=,
                                          ddo=,
                                          price=,
                                          timeout=)
            # TODO Listening for the publisher events from the events section of the service definition.

            return 201
        else:
            return 404
    except Exception as e:
        logging.error(e)
        return 500


@services.route('/consume', methods=['POST'])
def consume():
    """Allows download of asset data file.
    ---
    tags:
      - services
    consumes:
      - application/json
    parameters:
      - name: address
        in: query
        description: The consumer address.
        required: true
        type: string
      - name: serviceAgreementId
        in: query
        description: The service agreement id.
        required: true
        type: string
      - name: url
        in: query
        description: This URL is only valid if BRIZO acts as a proxy. Consumer can't download using the URL if it's not through Brizo.
        required: true
        type: string
    responses:
      200:
        description: Download valid url.
      400:
        description: One of the required attributes is missed.
      404:
        description: Invalid asset data.
      500:
        description: Error
    """
    data = request.args
    assert isinstance(data, dict), 'invalid `args` type, should already formatted into a dict.'
    # TODO Generation of the url
    try:
        did = ocn.get_did(data.get('serviceAgreementId'))
    except:
        return 404

    if ocn.checkPermissions(data.get('address', did)):
        # generate_sasl_url
        osm = Osmosis(config)
        osm.data_plugin
        return 200
    else:
        return 404

@services.route('/compute', methods=['POST'])
def compute():
    """Allows to execute an algorithm inside in a docker instance in the cloud aquarius.


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

    osm = Osmosis(config_file)
    # TODO use this two asigment in the exec_container to use directly did instead of the name
    # asset_url = _parse_url(get_metadata(ocn.assets.get_ddo(data.get('asset_did')))['base']['contentUrls'][0]).file
    # algorithm_url = _parse_url(
    #     get_metadata(ocn.assets.get_ddo(data.get('algorithm_url')))['base']['contentUrls'][0]).file
    # share_name_input = _parse_url(
    #     get_metadata(ocn.assets.get_ddo(data.get('asset_did')))['base']['contentUrls'][0]).file_share
    return osm.computing_plugin.exec_container(asset_url=data.get('asset_did'),
                                               algorithm_url=data.get('algorithm_did'),
                                               resource_group_name=config.get(ConfigSections.OSMOSIS,
                                                                              'azure.resource_group'),
                                               account_name=config.get(ConfigSections.OSMOSIS, 'azure.account.name'),
                                               account_key=config.get(ConfigSections.OSMOSIS, 'azure.account.key'),
                                               share_name_input=config.get(ConfigSections.OSMOSIS,
                                                                           'azure.share.input'),
                                               share_name_output=config.get(ConfigSections.OSMOSIS,
                                                                            'azure.share.output'),
                                               location=config.get(ConfigSections.OSMOSIS, 'azure.location'),
                                               # input_mount_point=data.get('input_mount_point'),
                                               # output_mount_point=data.get('output_mount_point'),
                                               docker_image=data.get('docker_image'),
                                               memory=data.get('memory'),
                                               cpu=data.get('cpu')), 200


def get_metadata(ddo):
    try:
        for service in ddo['service']:
            if service['type'] == 'Metadata':
                return service['metadata']
    except Exception as e:
        logging.error("Error getting the metatada: %s" % e)

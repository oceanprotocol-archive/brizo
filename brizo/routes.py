import logging
from flask import Blueprint, request
from squid_py.config import Config
from squid_py.ocean.ocean import Ocean
from squid_py.utils.utilities import split_signature
from brizo.constants import BaseURLs
from brizo.constants import ConfigSections
from brizo.log import setup_logging
from brizo.myapp import app
from osmosis_driver_interface.osmosis import Osmosis
from werkzeug.contrib.cache import SimpleCache

setup_logging()
services = Blueprint('services', __name__)

config_file = app.config['CONFIG_FILE']
config = Config(filename=config_file)
# Prepare keeper contracts for on-chain access control
# Prepare OceanDB
brizo_url = config.get(ConfigSections.RESOURCES, 'brizo.url')
brizo_url += BaseURLs.ASSETS_URL
ocn = Ocean(config_file=config_file)
cache = SimpleCache()


# TODO run in cases of brizo crash or you restart
# ocn.execute_pending_service_agreements()


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
            - consumerAddress:
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
            consumerAddress:
              description: Consumer address.
              type: string
              example: '0x00a329c0648769A73afAc7F9381E08FB43dBEA72'
    responses:
      201:
        description: Service agreement initialize successfully.
      400:
        description: One of the required attributes is missed.
      404:
        description: Invalid signature.
      500:
        description: Error
    """
    try:
      required_attributes = ['did', 'serviceAgreementId', 'serviceDefinitionId', 'signature', 'consumerAddress']
      assert isinstance(request.json, dict), 'invalid payload format.'
      logging.info('got "consume" request: %s' % request.json)
      data = request.json
      if not data:
          logging.error('Consume failed: data is empty.')
          return 'payload seems empty.', 400

      assert isinstance(data, dict), 'invalid `body` type, should already formatted into a dict.'
      logging.info('going to check required attributes')
      for attr in required_attributes:
          if attr not in data:
              logging.error('Consume failed: required attr %s missing.' % attr)
              return '"%s" is required for registering an asset.' % attr, 400   # Check signature
      if ocn.verify_service_agreement_signature(data.get('did'), data.get('serviceAgreementId'),
                                                data.get('serviceDefinitionId'),
                                                data.get('consumerAddress'), data.get('signature')):
        logging.info('SA signature is verified successfully')                                        
        cache.add(data.get('serviceAgreementId'), data.get('did'))
        # When you call execute agreement this start different listeners of the events to catch the paymentLocked.

        logging.info('getting publisher address')
        pub_address = config.get(ConfigSections.RESOURCES, 'publisher.address')
        if not pub_address:
            pub_address = list(ocn.get_accounts())[1]

        logging.info('going to execute SA')
        ocn.execute_service_agreement(service_agreement_id=data.get('serviceAgreementId'),
                                      service_definition_id=data.get('serviceDefinitionId'),
                                      service_agreement_signature=data.get('signature'),
                                      did=data.get('did'),
                                      consumer_address=data.get('consumerAddress'),
                                      publisher_address=pub_address

                                      )
        logging.info('executed SA')
        return "Service agreement initialize successfully", 201
      else:
        logging.info('invalid signature')
        return "Invalid signature", 404
    except Exception as e:
        logging.error(e)
        return "Error : " + str(e), 500


@services.route('/consume', methods=['GET'])
def consume():
    """Allows download of asset data file.
    ---
    tags:
      - services
    consumes:
      - application/json
    parameters:
      - name: consumerAddress
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
    try:
      data = request.args
      assert isinstance(data, dict), 'invalid `args` type, should already formatted into a dict.'
      # TODO check attributes
      if ocn.check_permissions(data.get('serviceAgreementId'), cache.get(data.get('serviceAgreementId')),
                              data.get('consumerAddress')):
          # generate_sasl_url
          cache.delete(data.get('serviceAgreementId'))
          osm = Osmosis(config_file)
          return osm.data_plugin.generate_url(data.get('url')), 200
      else:
          return "Invalid consumer address and/or service agreement id", 404
    except Exception as e:
        logging.error("Error- " + str(e))
        return "Error : " + str(e), 500


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

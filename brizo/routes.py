#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

import io
import logging
from os import getenv

from eth_utils import add_0x_prefix
from flask import Blueprint, request
from osmosis_driver_interface.osmosis import Osmosis
from squid_py.config import Config
from squid_py.did import id_to_did
from squid_py.exceptions import OceanDIDNotFound
from squid_py.http_requests.requests_session import get_requests_session
from squid_py.ocean.ocean import Ocean

from brizo.constants import ConfigSections
from brizo.log import setup_logging
from brizo.myapp import app

setup_logging()
services = Blueprint('services', __name__)

config_file = app.config['CONFIG_FILE']
config = Config(filename=config_file)
# Prepare keeper contracts for on-chain access control
# Prepare OceanDB
ocn = Ocean(config=config)
requests_session = get_requests_session()

logger = logging.getLogger('brizo')


# TODO run in cases of brizo crash or you restart
# ocn.execute_pending_service_agreements()

@services.route('/access/initialize', methods=['POST'])
def initialize():
    """Initialize the service agreement between the publisher and the consumer.

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
        description: Service agreement successfully initialized.
      400:
        description: One of the required attributes is missing.
      401:
        description: Error executing the service agreement.
      422:
        description: Ocean DID not found on chain.
      500:
        description: Error
    """
    required_attributes = ['did', 'serviceAgreementId', 'serviceDefinitionId', 'signature',
                           'consumerAddress']
    data = request.json
    msg, status = check_required_attributes(required_attributes, data, 'initialize')
    if msg:
        return msg, status
    try:

        logger.debug('Found ddo of did %s', data.get('did'))
        service_agreement_id = add_0x_prefix(data.get('serviceAgreementId'))
        # When you call execute agreement this start different listeners of the events to
        # catch the paymentLocked.
        did = data.get('did')
        asset = ocn.assets.resolve(did)
        publisher_acc = get_publisher_account()
        if config.has_option('resources', 'validate.creator'):
            if config.get('resources', 'validate.creator').lower() == 'true':
                if publisher_acc.address.lower() != asset.proof.get('creator', '').lower():
                    raise ValueError('Cannot serve asset service request because owner of '
                                     'requested asset is not recognized in this instance of Brizo.')

        success = ocn.agreements.create(
            did=did,
            service_definition_id=data.get('serviceDefinitionId'),
            agreement_id=service_agreement_id,
            service_agreement_signature=data.get('signature'),
            consumer_address=data.get('consumerAddress'),
            publisher_account=publisher_acc
        )

        logger.info('Done calling ocean.agreements.create, request payload was %s', data)
        if not success:
            msg = 'Failed to create agreement.'
            logger.error(msg)
            return msg, 401

        logger.info('Success creating service agreement')
        return "Service agreement successfully created", 201

    except OceanDIDNotFound as e:
        logger.error(e, exc_info=1)
        return "Requested did is not found in the keeper network: {}".format(str(e)), 422
    except Exception as e:
        logger.error(e, exc_info=1)
        return "Error: " + str(e), 500


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
        description: The ID of the service agreement.
        required: true
        type: string
      - name: url
        in: query
        description: This URL is only valid if Brizo acts as a proxy.
                     Consumer can't download using the URL if it's not through Brizo.
        required: true
        type: string
    responses:
      200:
        description: Redirect to valid asset url.
      400:
        description: One of the required attributes is missing.
      401:
        description: Invalid asset data.
      500:
        description: Error
    """
    data = request.args
    required_attributes = ['serviceAgreementId', 'consumerAddress', 'url']
    msg, status = check_required_attributes(required_attributes, data, 'consume')
    if msg:
        return msg, status
    try:
        if ocn.agreements.is_access_granted(
                data.get('serviceAgreementId'),
                id_to_did(ocn._keeper.agreement_manager.get_agreement(
                    data.get('serviceAgreementId')).did),
                data.get('consumerAddress')):
            logger.info('Connecting through Osmosis to generate the sign url.')
            try:
                osm = Osmosis(data.get('url'), config_file)
                download_url = osm.data_plugin.generate_url(data.get('url'))
                logger.debug("Osmosis generate the url: %s", download_url)
                try:
                    if request.range:
                        headers = {"Range": request.headers.get('range')}
                        response = requests_session.get(download_url, headers=headers)
                    else:
                        response = requests_session.get(download_url)
                    file = io.BytesIO(response.content)
                    return file.read(), response.status_code
                except Exception as e:
                    logger.error(e)
                    return "Error getting the url content: %s" % e, 401
            except Exception as e:
                logger.error(e)
                return "Error generating url: %s" % e, 401
        else:
            msg = "Invalid consumer address and/or service agreement id, " \
                  "or consumer address does not have permission to consume this asset."
            logger.warning(msg)
            return msg, 401
    except Exception as e:
        logger.error("Error- " + str(e))
        return "Error : " + str(e), 500


@services.route('/compute', methods=['POST'])
def compute():
    """Allows to execute an algorithm inside a Docker instance in the cloud. Requires the
    publisher of the assets to provide this service in the service agreement related with the
    requested `asset_did`.
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
              description: Identifier of the asset registered in Ocean
              type: string
              example: '0x0234242345'
            algorithm_did:
              description: Identifier of the algorithm to execute
              type: string
              example: '0x0234242345'
            consumer_wallet:
              description: Address of the wallet of the asset consumer. Ex. data-science...
              type: string
              example: '0x0234242345'
            docker_image:
              description: Docker image where the algorithm is going to be executed. Docker image
                           must include all the libraries needed to run it.
              type: string
              example: python:3.6-alpine
            memory:
              description: Ammout of memory in GB to run the algorithm
              type: number
              example: 1.5
            cpu:
              description: Number of CPUs to execute the algorithm.
              type: integer
              example: 1
    """
    required_attributes = ['asset_did', 'algorithm_did', 'consumer_wallet']
    data = request.json
    msg, status = check_required_attributes(required_attributes, data, 'compute')
    if msg:
        return msg, status
    osm = Osmosis(config_file)
    # TODO use this two asigment in the exec_container to use directly did instead of the name
    # asset_url = _parse_url(get_metadata(ocn.assets.get_ddo(data.get('asset_did')))['base'][
    # 'contentUrls'][0]).file
    # algorithm_url = _parse_url(
    #     get_metadata(ocn.assets.get_ddo(data.get('algorithm_url')))['base']['contentUrls'][
    #     0]).file
    # share_name_input = _parse_url(
    #     get_metadata(ocn.assets.get_ddo(data.get('asset_did')))['base']['contentUrls'][
    #     0]).file_share
    return osm.computing_plugin.exec_container(asset_url=data.get('asset_did'),
                                               algorithm_url=data.get('algorithm_did'),
                                               resource_group_name=get_env_property(
                                                   'AZURE_RESOURCE_GROUP', 'azure.resource_group'),
                                               account_name=get_env_property('AZURE_ACCOUNT_NAME',
                                                                             'azure.account.name'),
                                               account_key=get_env_property('AZURE_ACCOUNT_KEY',
                                                                            'azure.account.key'),
                                               share_name_input=get_env_property(
                                                   'AZURE_SHARE_INPUT', 'azure.share.input'),
                                               share_name_output=get_env_property(
                                                   'AZURE_SHARE_OUTPUT', 'azure.share.output'),
                                               location=get_env_property('AZURE_LOCATION',
                                                                         'azure.location'),
                                               # input_mount_point=data.get('input_mount_point'),
                                               # output_mount_point=data.get('output_mount_point'),
                                               docker_image=data.get('docker_image'),
                                               memory=data.get('memory'),
                                               cpu=data.get('cpu')), 200


def check_required_attributes(required_attributes, data, method):
    assert isinstance(data, dict), 'invalid payload format.'
    logger.info('got %s request: %s' % (method, data))
    if not data:
        logger.error('%s request failed: data is empty.' % method)
        return 'payload seems empty.', 400
    for attr in required_attributes:
        if attr not in data:
            logger.error('%s request failed: required attr %s missing.' % (method, attr))
            return '"%s" is required in the call to %s' % (attr, method), 400
    return None, None


def get_metadata(ddo):
    try:
        for service in ddo['service']:
            if service['type'] == 'Metadata':
                return service['metadata']
    except Exception as e:
        logger.error("Error getting the metatada: %s" % e)


def get_env_property(env_variable, property_name):
    return getenv(env_variable,
                  config.get(ConfigSections.OSMOSIS, property_name))


def get_publisher_account():
    address = config.parity_address
    logger.info(f'address: {address}, {ocn.accounts.accounts_addresses}')
    for acc in ocn.accounts.list():
        if acc.address.lower() == address.lower():
            return acc

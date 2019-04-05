#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

import io
import json
import logging

from eth_utils import add_0x_prefix
from flask import Blueprint, request
from osmosis_driver_interface.osmosis import Osmosis
from squid_py import ConfigProvider
from squid_py.config import Config
from squid_py.did import id_to_did
from squid_py.exceptions import OceanDIDNotFound
from squid_py.http_requests.requests_session import get_requests_session
from squid_py.keeper import Keeper
from squid_py.ocean.ocean import Ocean

from brizo.log import setup_logging
from brizo.myapp import app
from brizo.util import (check_required_attributes, get_provider_account)

setup_logging()
services = Blueprint('services', __name__)

config_file = app.config['CONFIG_FILE']
config = Config(filename=config_file)
ConfigProvider.set_config(config)
# Prepare keeper contracts for on-chain access control
# Prepare OceanDB
ocn = Ocean()
requests_session = get_requests_session()

logger = logging.getLogger('brizo')


# TODO run in cases of brizo crash or you restart
# ocn.execute_pending_service_agreements()


@services.route('/publish', methods=['POST'])
def publish():
    """Encrypt document using the SecretStore and keyed by the given documentId.

    This can be used by the publisher of an asset to encrypt the urls of the
    asset data files before publishing the asset ddo. The publisher to use this
    service is one that is using a front-end with a wallet app such as MetaMask.
    In such scenario the publisher is not able to encrypt the urls using the
    SecretStore interface and this service becomes necessary.

    tags:
      - services
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        description: Asset urls encryption.
        schema:
          type: object
          required:
            - documentId
            - signedDocumentId
            - document
            - publisherAddress:
          properties:
            documentId:
              description: Identifier of the asset to be registered in ocean.
              type: string
              example: 'did:op:08a429b8529856d59867503f8056903a680935a76950bb9649785cc97869a43d'
            signedDocumentId:
              description: Publisher signature of the documentId
              type: string
              example: ''
            document:
              description: document
              type: string
              example: '/some-url'
            publisherAddress:
              description: Publisher address.
              type: string
              example: '0x00a329c0648769A73afAc7F9381E08FB43dBEA72'
    responses:
      201:
        description: document successfully encrypted.
      500:
        description: Error

    return: the encrypted document (hex str)
    """
    required_attributes = [
        'documentId',
        'signedDocumentId',
        'document',
        'publisherAddress'
    ]
    data = request.json
    msg, status = check_required_attributes(required_attributes, data, 'publish')
    if msg:
        return msg, status

    provider_acc = get_provider_account(ocn)
    did = data.get('documentId')
    signed_did = data.get('signedDocumentId')
    document = data.get('document')
    publisher_address = data.get('publisherAddress')

    try:
        address = Keeper.get_instance().ec_recover(did, signed_did)
        if address.lower() != publisher_address.lower():
            msg = f'Invalid signature {signed_did} for ' \
                f'publisherAddress {publisher_address} and documentId {did}.'
            raise ValueError(msg)

        encrypted_document = ocn.secret_store.encrypt(did, document, provider_acc)
        logger.info(f'encrypted urls {encrypted_document}, '
                    f'publisher {publisher_address}, '
                    f'documentId {did}')
        return encrypted_document, 201
    except Exception as e:
        logger.error(
            f'Error encrypting document: {e}. \nPayload was: documentId={did}, '
            f'publisherAddress={publisher_address}',
            exc_info=1
        )
        return "Error: " + str(e), 500


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
    required_attributes = [
        'did',
        'serviceAgreementId',
        'serviceDefinitionId',
        'signature',
        'consumerAddress'
    ]
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
        provider_acc = get_provider_account(ocn)
        if config.has_option('resources', 'validate.creator'):
            if config.get('resources', 'validate.creator').lower() == 'true':
                if provider_acc.address.lower() != asset.proof.get('creator', '').lower():
                    raise ValueError('Cannot serve asset service request because owner of '
                                     'requested asset is not recognized in this instance of Brizo.')

        success = ocn.agreements.create(
            did=did,
            service_definition_id=data.get('serviceDefinitionId'),
            agreement_id=service_agreement_id,
            service_agreement_signature=data.get('signature'),
            consumer_address=data.get('consumerAddress'),
            publisher_account=provider_acc
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
    required_attributes = [
        'serviceAgreementId',
        'consumerAddress'
    ]
    msg, status = check_required_attributes(required_attributes, data, 'consume')
    if msg:
        return msg, status

    if not (data.get('url') or (data.get('signature') and data.get('index'))):
        return f'Either `url` or `signature and index` are required in the call to "consume".', 400

    try:
        provider_account = get_provider_account(ocn)
        agreement_id = data.get('serviceAgreementId')
        consumer_address = data.get('consumerAddress')
        asset_id = ocn.agreements.get(agreement_id).did
        did = id_to_did(asset_id)
        if ocn.agreements.is_access_granted(
                agreement_id,
                did,
                consumer_address):
            logger.info('Connecting through Osmosis to generate the sign url.')
            url = data.get('url')
            try:
                if not url:
                    signature = data.get('signature')
                    index = int(data.get('index'))
                    address = Keeper.get_instance().ec_recover(agreement_id, signature)
                    if address.lower() != consumer_address.lower():
                        msg = f'Invalid signature {signature} for ' \
                            f'consumerAddress {consumer_address} and documentId {did}.'
                        raise ValueError(msg)

                    asset = ocn.assets.resolve(did)
                    urls_str = ocn.secret_store.decrypt(
                        asset_id, asset.encrypted_files, provider_account
                    )
                    urls = json.loads(urls_str)
                    if index >= len(urls):
                        raise ValueError(f'url index "{index}"" is invalid.')
                    url = urls[index]['url']

                osm = Osmosis(url, config_file)
                download_url = osm.data_plugin.generate_url(url)
                logger.debug("Osmosis generate the url: %s", download_url)
                try:
                    if request.range:
                        headers = {"Range": request.headers.get('range')}
                        response = requests_session.get(download_url, headers=headers, stream=True)
                    else:
                        response = requests_session.get(download_url, stream=True)
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

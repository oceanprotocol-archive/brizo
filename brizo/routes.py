#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

import json
import logging

from eth_utils import remove_0x_prefix
from flask import Blueprint, request
from ocean_utils.did import id_to_did
from ocean_utils.did_resolver.did_resolver import DIDResolver
from ocean_utils.http_requests.requests_session import get_requests_session
from secret_store_client.client import RPCError

from brizo.log import setup_logging
from brizo.myapp import app
from brizo.util import (
    check_required_attributes,
    get_provider_account,
    verify_signature,
    get_asset_url_at_index,
    get_download_url,
    build_download_response,
    is_access_granted,
    do_secret_store_encrypt,
    get_config,
    keeper_instance, setup_keeper)

setup_logging()
services = Blueprint('services', __name__)
setup_keeper(app.config['CONFIG_FILE'])
provider_acc = get_provider_account()
requests_session = get_requests_session()

logger = logging.getLogger(__name__)


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
            - signature
            - document
            - publisherAddress:
          properties:
            documentId:
              description: Identifier of the asset to be registered in ocean.
              type: string
              example: 'did:op:08a429b8529856d59867503f8056903a680935a76950bb9649785cc97869a43d'
            signature:
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
        'signature',
        'document',
        'publisherAddress'
    ]
    data = request.json
    if 'signedDocumentId' in data and 'signature' not in data:
        data['signature'] = data['signedDocumentId']

    msg, status = check_required_attributes(required_attributes, data, 'publish')
    if msg:
        return msg, status

    did = data.get('documentId')
    signature = data.get('signature')
    document = json.dumps(json.loads(data.get('document')), separators=(',', ':'))
    publisher_address = data.get('publisherAddress')

    try:
        if not verify_signature(keeper_instance(), publisher_address, signature, did):
            msg = f'Invalid signature {signature} for ' \
                f'publisherAddress {publisher_address} and documentId {did}.'
            raise ValueError(msg)

        encrypted_document = do_secret_store_encrypt(
            remove_0x_prefix(did),
            document,
            provider_acc,
            get_config()
        )
        logger.info(f'encrypted urls {encrypted_document}, '
                    f'publisher {publisher_address}, '
                    f'documentId {did}')
        return encrypted_document, 201

    except (RPCError, Exception) as e:
        logger.error(
            f'SecretStore Error: {e}. \n'
            f'providerAddress={provider_acc.address}\n'
            f'Payload was: documentId={did}, '
            f'publisherAddress={publisher_address},'
            f'signature={signature}',
            exc_info=1
        )
        return f'Error: {str(e)}', 500


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
        keeper = keeper_instance()
        agreement_id = data.get('serviceAgreementId')
        consumer_address = data.get('consumerAddress')
        asset_id = keeper.agreement_manager.get_agreement(agreement_id).did
        did = id_to_did(asset_id)

        if not is_access_granted(
                agreement_id,
                did,
                consumer_address,
                keeper):
            msg = ('Checking access permissions failed. Either consumer address does not have '
                   'permission to consume this asset or consumer address and/or service agreement '
                   'id is invalid.')
            logger.warning(msg)
            return msg, 401

        asset = DIDResolver(keeper.did_registry).resolve(did)
        content_type = None
        url = data.get('url')
        if not url:
            signature = data.get('signature')
            index = int(data.get('index'))
            if not verify_signature(keeper, consumer_address, signature, agreement_id):
                msg = f'Invalid signature {signature} for ' \
                    f'publisherAddress {consumer_address} and documentId {agreement_id}.'
                raise ValueError(msg)

            file_attributes = asset.metadata['base']['files'][index]
            content_type = file_attributes.get('contentType', None)
            url = get_asset_url_at_index(index, asset, provider_acc)

        download_url = get_download_url(url, app.config['CONFIG_FILE'])
        logger.info(f'Done processing consume request for asset {did}, agreementId {agreement_id},'
                    f' url {download_url}')
        return build_download_response(request, requests_session, url, download_url, content_type)
    except (ValueError, Exception) as e:
        logger.error(f'Error- {str(e)}', exc_info=1)
        return f'Error : {str(e)}', 500

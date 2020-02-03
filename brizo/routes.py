#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

import json
import logging

from eth_utils import remove_0x_prefix
from flask import Blueprint, jsonify, request, Response
from ocean_utils.did import id_to_did
from ocean_utils.did_resolver.did_resolver import DIDResolver
from ocean_utils.http_requests.requests_session import get_requests_session
from secret_store_client.client import RPCError

from brizo.exceptions import InvalidSignatureError
from brizo.log import setup_logging
from brizo.myapp import app
from brizo.util import (
    build_download_response,
    check_required_attributes,
    do_secret_store_encrypt,
    get_asset_url_at_index,
    get_asset_urls,
    get_config,
    get_download_url,
    get_provider_account,
    is_access_granted,
    keeper_instance,
    setup_keeper,
    verify_signature,
    get_compute_endpoint,
    build_stage_algorithm_dict, build_stage_output_dict, build_stage_dict, validate_algorithm_dict, get_request_data)

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
    data = get_request_data(request)
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
        # Raises ValueError when signature is invalid
        verify_signature(keeper_instance(), publisher_address, signature, did)

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

    except InvalidSignatureError as e:
        msg = f'Publisher signature failed verification: {e}'
        logger.error(msg, exc_info=1)
        return msg, 401

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
      - name: signature
        in: query
        description: Signature of the documentId to verify that the consumer has rights to download the asset.
      - name: index
        in: query
        description: Index of the file in the array of files.
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
    data = get_request_data(request)
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
            verify_signature(keeper, consumer_address, signature, agreement_id)

            file_attributes = asset.metadata['main']['files'][index]
            content_type = file_attributes.get('contentType', None)
            url = get_asset_url_at_index(index, asset, provider_acc)

        download_url = get_download_url(url, app.config['CONFIG_FILE'])
        logger.info(f'Done processing consume request for asset {did}, agreementId {agreement_id},'
                    f' url {download_url}')
        return build_download_response(request, requests_session, url, download_url, content_type)

    except InvalidSignatureError as e:
        msg = f'Consumer signature failed verification: {e}'
        logger.error(msg, exc_info=1)
        return msg, 401

    except (ValueError, Exception) as e:
        logger.error(f'Error- {str(e)}', exc_info=1)
        return f'Error : {str(e)}', 500


@services.route('/compute', methods=['DELETE'])
def compute_delete_job():
    """Deletes a workflow.

    ---
    tags:
      - services
    consumes:
      - application/json
    parameters:
      - name: signature
        in: query
        description: Signature of the documentId to verify that the consumer has rights to download the asset.
        type: string
      - name: serviceAgreementId
        in: query
        description: The ID of the service agreement.
        required: true
        type: string
      - name: consumerAddress
        in: query
        description: The consumer address.
        required: true
        type: string
      - name: jobId
        in: query
        description: JobId.
        type: string
    responses:
      200:
        description: Call to the operator-service was successful.
      400:
        description: One of the required attributes is missing.
      401:
        description: Invalid asset data.
      500:
        description: Error
    """
    data = get_request_data(request)
    required_attributes = [
        'signature'
    ]
    msg, status = check_required_attributes(required_attributes, data, 'compute')
    if msg:
        return msg, status

    if not (data.get('signature')):
        return f'`signature is required in the call to "consume".', 400

    # TODO  - check incoming signature
    try:
        agreement_id = data.get('serviceAgreementId')
        owner = data.get('consumerAddress')
        job_id = data.get('jobId')
        body = dict()
        if owner is not None:
            body['owner'] = owner
        if job_id is not None:
            body['jobId'] = job_id
        if agreement_id is not None:
            body['agreementId'] = agreement_id

        # TODO - add signature so operator can check auth
        response = requests_session.delete(
            get_compute_endpoint(),
            params=body,
            headers={'content-type': 'application/json'})
        return response.content

    except (ValueError, Exception) as e:
        logger.error(f'Error- {str(e)}', exc_info=1)
        return f'Error : {str(e)}', 500


@services.route('/compute', methods=['PUT'])
def compute_stop_job():
    """Stop the execution of a workflow.

    ---
    tags:
      - services
    consumes:
      - application/json
    parameters:
      - name: signature
        in: query
        description: Signature of the documentId to verify that the consumer has rights to download the asset.
        type: string
      - name: serviceAgreementId
        in: query
        description: The ID of the service agreement.
        required: true
        type: string
      - name: consumerAddress
        in: query
        description: The consumer address.
        required: true
        type: string
      - name: jobId
        in: query
        description: JobId.
        type: string
    responses:
      200:
        description: Call to the operator-service was successful.
      400:
        description: One of the required attributes is missing.
      401:
        description: Invalid asset data.
      500:
        description: Error
    """
    data = get_request_data(request)
    required_attributes = [
        'signature'
    ]
    msg, status = check_required_attributes(required_attributes, data, 'compute')
    if msg:
        return msg, status

    if not (data.get('signature')):
        return f'`signature is required in the call to "consume".', 400

    # TODO  - check incoming signature
    try:
        agreement_id = data.get('serviceAgreementId')
        owner = data.get('consumerAddress')
        job_id = data.get('jobId')
        body = dict()
        if owner is not None:
            body['owner'] = owner
        if job_id is not None:
            body['jobId'] = job_id
        if agreement_id is not None:
            body['agreementId'] = agreement_id
        # TODO - add signature so operator can check auth
        response = requests_session.put(
            get_compute_endpoint(),
            params=body,
            headers={'content-type': 'application/json'})
        return response.content

    except (ValueError, Exception) as e:
        logger.error(f'Error- {str(e)}', exc_info=1)
        return f'Error : {str(e)}', 500


@services.route('/compute', methods=['GET'])
def compute_get_status_job():
    """Get status for a specific jobid/agreementId/owner

    ---
    tags:
      - services
    consumes:
      - application/json
    parameters:
      - name: signature
        in: query
        description: Signature of the documentId to verify that the consumer has rights to download the asset.
        type: string
      - name: serviceAgreementId
        in: query
        description: The ID of the service agreement.
        required: true
        type: string
      - name: consumerAddress
        in: query
        description: The consumer address.
        required: true
        type: string
      - name: jobId
        in: query
        description: JobId.
        type: string
    responses:
      200:
        description: Call to the operator-service was successful.
      400:
        description: One of the required attributes is missing.
      401:
        description: Invalid asset data.
      500:
        description: Error
    """
    data = get_request_data(request)
    required_attributes = [
        'signature'
    ]
    msg, status = check_required_attributes(required_attributes, data, 'compute')
    if msg:
        return msg, status

    if not (data.get('signature')):
        return f'`signature is required in the call to "consume".', 400

    # TODO  - check incoming signature
    try:
        agreement_id = data.get('serviceAgreementId')
        owner = data.get('consumerAddress')
        job_id = data.get('jobId')
        body = dict()
        if owner is not None:
            body['owner'] = owner
        if job_id is not None:
            body['jobId'] = job_id
        if agreement_id is not None:
            body['agreementId'] = agreement_id

        body["signature"] = keeper_instance().sign_hash(agreement_id, provider_acc)
        response = requests_session.get(
            get_compute_endpoint(),
            params=body,
            headers={'content-type': 'application/json'})
        return response.content

    except (ValueError, Exception) as e:
        logger.error(f'Error- {str(e)}', exc_info=1)
        return f'Error : {str(e)}', 500


@services.route('/compute', methods=['POST'])
def compute_start_job():
    """Call the execution of a workflow.

    ---
    tags:
      - services
    consumes:
      - application/json
    parameters:
      - name: signature
        in: query
        description: Signature of the documentId to verify that the consumer has rights to run the compute service..
        type: string
      - name: serviceAgreementId
        in: query
        description: The ID of the service agreement on-chain
        required: true
        type: string
      - name: consumerAddress
        in: query
        description: The consumer ethereum address.
        required: true
        type: string
      - name: algorithmDid
        in: query
        description: hex str the did of the algorithm to be executed
        required: false
        type: string
      - name: algorithmMeta
        in: query
        description: json object that define the algorithm attributes and url or raw code
        required: false
        type: string
    responses:
      200:
        description: Call to the operator-service was successful.
      400:
        description: One of the required attributes is missing.
      401:
        description: Invalid asset data.
      500:
        description: Error
    """
    data = get_request_data(request)
    required_attributes = [
        'signature',
        'serviceAgreementId',
        'consumerAddress'
    ]
    msg, status = check_required_attributes(required_attributes, data, 'compute')
    if msg:
        return msg, status

    agreement_id = data.get('serviceAgreementId')
    consumer_address = data.get('consumerAddress')
    signature = data.get('signature')
    algorithm_did = data.get('algorithmDid')
    algorithm_meta = data.get('algorithmMeta')

    try:
        keeper = keeper_instance()
        # Validate algorithm info
        if not (algorithm_meta or algorithm_did):
            msg = f'Need an `algorithmMeta` or `algorithmDid` to run, otherwise don\'t bother.'
            logger.error(msg, exc_info=1)
            return jsonify(error=msg), 400

        # Consumer signature
        verify_signature(keeper, consumer_address, signature, agreement_id)

        #########################
        # ALGORITHM
        algorithm_dict = build_stage_algorithm_dict(algorithm_did, algorithm_meta, provider_acc)
        error_msg, status_code = validate_algorithm_dict(algorithm_dict, algorithm_did)
        if error_msg:
            return jsonify(error=error_msg), status_code

        #########################
        # INPUT
        asset_id = keeper.agreement_manager.get_agreement(agreement_id).did
        did = id_to_did(asset_id)
        asset = DIDResolver(keeper.did_registry).resolve(did)
        asset_urls = get_asset_urls(asset, provider_acc, app.config['CONFIG_FILE'])
        if not asset_urls:
            return jsonify(error=f'cannot get url(s) in input did {did}.'), 400

        input_dict = dict({
            'index': 0,
            'id': did,
            'url': asset_urls
        })

        #########################
        # OUTPUT
        output_dict = build_stage_output_dict(asset, consumer_address, provider_acc)

        #########################
        # STAGE
        stage = build_stage_dict(input_dict, algorithm_dict, output_dict)

        #########################
        # WORKFLOW
        workflow = dict({'stages': list([stage])})

        # workflow is ready, push it to operator
        logger.info('Sending: %s', workflow)

        payload = {
            "workflow": workflow,
            "signature": keeper.sign_hash(agreement_id, provider_acc),
            'agreementId': agreement_id,
            'owner': consumer_address,
        }
        response = requests_session.post(
            get_compute_endpoint(),
            data=json.dumps(payload),
            headers={'content-type': 'application/json'})

        return Response(
            response.content,
            response.status_code,
            headers={'content-type': 'application/json'}
        )

    except InvalidSignatureError as e:
        msg = f'Consumer signature failed verification: {e}'
        logger.error(msg, exc_info=1)
        return msg, 401

    except (ValueError, KeyError, Exception) as e:
        logger.error(f'Error- {str(e)}', exc_info=1)
        return f'Error : {str(e)}', 500

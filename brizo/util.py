import json
import logging
import traceback
from os import getenv
import io

from eth_utils import add_0x_prefix
from osmosis_driver_interface.osmosis import Osmosis
from flask import Response
from squid_py import ConfigProvider, Ocean
from squid_py.agreements.register_service_agreement import register_service_agreement_publisher
from squid_py.agreements.service_agreement import ServiceAgreement
from squid_py.agreements.service_types import ServiceTypes
from squid_py.data_store.agreements import AgreementsStorage
from squid_py.did import id_to_did, did_to_id
from squid_py.keeper import Keeper
from squid_py.keeper.web3_provider import Web3Provider

from brizo.constants import ConfigSections

logger = logging.getLogger(__name__)


def handle_agreement_created(event, *_):
    if not event or not event.args:
        logger.debug('handle_agreement_created: empty event')
        return

    logger.debug(f'handle_agreement_created: checking if should handle this event, event_args={event.args}')
    try:
        config = ConfigProvider.get_config()
        agreement_id = Web3Provider.get_web3().toHex(event.args["_agreementId"])
        ids = AgreementsStorage(config.storage_path).get_agreement_ids()
        if ids:
            # logger.info(f'got agreement ids: #{agreement_id}#, ##{ids}##, \nid in ids: {agreement_id in ids}')
            if agreement_id in ids:
                logger.debug(f'handle_agreement_created: skipping service agreement {agreement_id} '
                             f'because it already been processed before.')
                return

        logger.info(f'Start handle_agreement_created: event_args={event.args}')
        ocean = Ocean()
        provider_account = get_provider_account(ocean)
        assert provider_account.address == event.args["_accessProvider"]
        did = id_to_did(event.args["_did"])
        ddo = ocean.assets.resolve(did)
        sa = ServiceAgreement.from_ddo(ServiceTypes.ASSET_ACCESS, ddo)

        condition_ids = sa.generate_agreement_condition_ids(
            agreement_id=agreement_id,
            asset_id=add_0x_prefix(did_to_id(did)),
            consumer_address=event.args["_accessConsumer"],
            publisher_address=ddo.publisher,
            keeper=Keeper.get_instance())
        register_service_agreement_publisher(
            config.storage_path,
            event.args["_accessConsumer"],
            agreement_id,
            did,
            sa,
            sa.service_definition_id,
            sa.get_price(),
            provider_account,
            condition_ids
        )
        logger.info(f'handle_agreement_created() -- done registering event listeners.')
    except Exception as e:
        logger.error(f'Error in handle_agreement_created: {e}\n{traceback.format_exc()}')
    finally:
        logger.debug(f'handle_agreement_created() -- EXITing.')


def verify_signature(ocn, keeper, signer_address, signature, original_msg):
    if ocn.auth.is_token_valid(signature):
        address = ocn.auth.check(signature)
    else:
        address = keeper.ec_recover(original_msg, signature)

    return address.lower() == signer_address.lower()


def get_provider_account(ocean_instance):
    address = ConfigProvider.get_config().parity_address
    logger.info(f'address: {address}, {ocean_instance.accounts.accounts_addresses}')
    for acc in ocean_instance.accounts.list():
        if acc.address.lower() == address.lower():
            return acc


def get_env_property(env_variable, property_name):
    return getenv(
        env_variable,
        ConfigProvider.get_config().get(ConfigSections.OSMOSIS, property_name)
    )


def get_metadata(ddo):
    try:
        for service in ddo['service']:
            if service['type'] == 'Metadata':
                return service['metadata']
    except Exception as e:
        logger.error("Error getting the metatada: %s" % e)


def build_download_response(request, requests_session, url, download_url):
    try:
        if request.range:
            headers = {"Range": request.headers.get('range')}
        else:
            headers = {
                "Content-Disposition": f'attachment;filename={url.split("/")[-1]}',
                "Access-Control-Expose-Headers": f'Content-Disposition'
            }

        response = requests_session.get(download_url, headers=headers, stream=True)
        return Response(
            io.BytesIO(response.content).read(),
            response.status_code,
            headers=headers
        )
    except Exception as e:
        logger.error(f'Error preparing file download response: {str(e)}')
        raise


def get_asset_url_at_index(ocean_instance, url_index, did, account):
    logger.debug(f'get_asset_url_at_index(): url_index={url_index}, did={did}, provider={account.address}')
    try:
        asset = ocean_instance.assets.resolve(did)
        files_str = ocean_instance.secret_store.decrypt(
            asset.asset_id, asset.encrypted_files, account
        )
        logger.debug(f'Got decrypted files str {files_str}')
        files_list = json.loads(files_str)
        if url_index >= len(files_list):
            raise ValueError(f'url index "{url_index}"" is invalid.')

        file_meta_dict = files_list[url_index]
        if not file_meta_dict or not isinstance(file_meta_dict, dict):
            raise TypeError(f'Invalid file meta at index {url_index}, expected a dict, got a '
                            f'{type(file_meta_dict)}.')
        if 'url' not in file_meta_dict:
            raise ValueError(f'The "url" key is not found in the file dict {file_meta_dict} at index {url_index}.')

        return file_meta_dict['url']

    except Exception as e:
        logger.error(f'Error decrypting url at index {url_index} for asset {did}: {str(e)}')
        raise


def get_download_url(url, config_file):
    try:
        logger.info('Connecting through Osmosis to generate the signed url.')
        osm = Osmosis(url, config_file)
        download_url = osm.data_plugin.generate_url(url)
        logger.debug(f'Osmosis generated the url: {download_url}')
        return download_url
    except Exception as e:
        logger.error(f'Error generating Osmosis url: {str(e)}')
        raise


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


def check_and_register_agreement_template(ocean_instance, keeper, account):
    if keeper.template_manager.get_num_templates() == 0:
        ocean_instance.templates.propose(
            keeper.escrow_access_secretstore_template.address,
            account)
        ocean_instance.templates.approve(
            keeper.escrow_access_secretstore_template.address,
            account)

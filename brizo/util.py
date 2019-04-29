import logging
from os import getenv

from eth_utils import add_0x_prefix
from squid_py import ConfigProvider, Ocean
from squid_py.agreements.register_service_agreement import register_service_agreement_publisher
from squid_py.agreements.service_agreement import ServiceAgreement
from squid_py.agreements.service_types import ServiceTypes
from squid_py.did import id_to_did, did_to_id
from squid_py.keeper import Keeper
from squid_py.keeper.web3_provider import Web3Provider

from brizo.constants import ConfigSections

logger = logging.getLogger(__name__)


def handle_agreement_created(event, *_):
    if not event or not event.args:
        return

    logger.debug(f'Start handle_agreement_created: event_args={event.args}')
    config = ConfigProvider.get_config()
    ocean = Ocean()
    provider_account = get_provider_account(ocean)
    assert provider_account.address == event.args["_accessProvider"]
    did = id_to_did(event.args["_did"])
    agreement_id = Web3Provider.get_web3().toHex(event.args["_agreementId"])

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
    logger.debug(f'handle_agreement_created() -- done registering event listeners.')


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

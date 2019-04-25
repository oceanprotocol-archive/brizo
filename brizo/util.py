import logging
from os import getenv

from squid_py import ConfigProvider, Ocean
from squid_py.agreements.register_service_agreement import register_service_agreement_publisher
from squid_py.agreements.service_agreement import ServiceAgreement
from squid_py.agreements.service_types import ServiceTypes
from squid_py.did import id_to_did
from squid_py.keeper import Keeper

from brizo.constants import ConfigSections

logger = logging.getLogger(__name__)


def handle_agreement_created(event, *_):
    if not event or not event.args:
        return

    config = ConfigProvider.get_config()
    ocean = Ocean()
    did = id_to_did(event.args["_did"])
    ddo = ocean.assets.resolve(did)
    sa = ServiceAgreement.from_ddo(ServiceTypes.ASSET_ACCESS, ddo)
    register_service_agreement_publisher(
        config.storage_path,
        event.args["_accessConsumer"],
        event.args["_agreementId"],
        did,
        sa,
        sa.service_definition_id,
        sa.get_price(),
        event.args["_accessProvider"],
        sa.generate_agreement_condition_ids(
            agreement_id=event.args["_agreementId"],
            asset_id=event.args["_did"],
            consumer_address=event.args["_accessConsumer"],
            publisher_address=ddo.publisher,
            keeper=Keeper.get_instance())
    )


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

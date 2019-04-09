import logging
from os import getenv

from squid_py import ConfigProvider
from brizo.constants import ConfigSections

logger = logging.getLogger(__name__)


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

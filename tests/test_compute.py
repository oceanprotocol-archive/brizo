#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

import json
from os import getenv

from osmosis_driver_interface.osmosis import Osmosis
from osmosis_driver_interface.utils import parse_config

from brizo.constants import BaseURLs
from tests.conftest import json_brizo


def test_compute_on_cloud(client):
    # disable compute until it is supported in next release.
    return
    osm = Osmosis(file_path='config_local.ini')
    config = parse_config(file_path='config_local.ini')
    elements_before_compute = len(
        osm.data_plugin.list(get_env_property(config, 'AZURE_SHARE_OUTPUT', 'azure.share.output'),
                             False,
                             get_env_property(config, 'AZURE_ACCOUNT_NAME', 'azure.account.name')
                             ))
    post = client.post(BaseURLs.BASE_BRIZO_URL + '/services/compute',
                       data=json.dumps(json_brizo),
                       content_type='application/json')
    assert len(
        osm.data_plugin.list(get_env_property(config, 'AZURE_SHARE_OUTPUT', 'azure.share.output'),
                             False,
                             get_env_property(config, 'AZURE_ACCOUNT_NAME',
                                              'azure.account.name'))) == elements_before_compute + 1
    osm.data_plugin.delete(
        'https://testocnfiles.file.core.windows.net/output/' + post.data.decode('utf-8'))


def get_env_property(config, env_variable, property_name):
    return getenv(env_variable,
                  config.get(property_name))

import json

from brizo.constants import BaseURLs
from osmosis_driver_interface.osmosis import Osmosis
from tests.conftest import json_brizo
from osmosis_driver_interface.utils import parse_config


def test_compute_on_cloud(client):
    osm = Osmosis(file_path='config_local.ini')
    config = parse_config(file_path='config_local.ini')
    elements_before_compute = len(osm.data_plugin.list(config.get('azure.share.output'),
                                                       False,
                                                       config.get('azure.account.name')
                                                       ))
    post = client.post(BaseURLs.BASE_BRIZO_URL + '/services/compute',
                       data=json.dumps(json_brizo),
                       content_type='application/json')
    assert len(osm.data_plugin.list(config.get('azure.share.output'),
                                    False,
                                    config.get('azure.account.name'))) == elements_before_compute + 1
    osm.data_plugin.delete('https://testocnfiles.file.core.windows.net/output/' + post.data.decode('utf-8'))

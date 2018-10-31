import json

from brizo.constants import BaseURLs
from brizo.osmosis import Osmosis
from tests.conftest import json_brizo


def test_compute_on_cloud(client):
    osm = Osmosis(config_file='config_local.ini')
    elements_before_compute = len(osm.list_file_shares(osm.config.get('resources', 'azure.account.name'),
                                                       osm.config.get('resources', 'azure.account.key'),
                                                       osm.config.get('resources', 'azure.share.output')))
    post = client.post(BaseURLs.BASE_BRIZO_URL + '/services/exec',
                       data=json.dumps(json_brizo),
                       content_type='application/json')
    assert len(osm.list_file_shares(osm.config.get('resources', 'azure.account.name'),
                                    osm.config.get('resources', 'azure.account.key'),
                                    osm.config.get('resources', 'azure.share.output'))) == elements_before_compute + 1
    osm.delete_file_share(osm.config.get('resources', 'azure.account.name'),
                          osm.config.get('resources', 'azure.account.key'),
                          osm.config.get('resources', 'azure.share.output'),
                          post.data.decode('utf-8'))

import os, sys, time
from datetime import datetime, timedelta

from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.mgmt.containerinstance.models import (ContainerGroup, Container, ContainerPort, Port, IpAddress,
                                                 ResourceRequirements, ResourceRequests, ContainerGroupNetworkProtocol, OperatingSystemTypes)

from azure.mgmt.resource import ResourceManagementClient
from azure.storage.blob import BlobPermissions
from azure.storage.blob import BlockBlobService
from azure.storage.file import FileService


class Osmosis(object):
    os.environ["AZURE_CLIENT_ID"] = "8c92f07f-7030-430f-9abb-f5a1b1fe5da3"
    os.environ["AZURE_CLIENT_SECRET"] = "RBO5+eignW7ar5er7WgUCr0UJxdjsOw/8zyPmR2Y8Uk="
    os.environ["AZURE_TENANT_ID"] = "4a4a3787-4e2e-4a32-8006-6e2b5877640e"
    os.environ["AZURE_SUBSCRIPTION_ID"] = "369284be-0104-421a-8488-1aeac0caecaa"

    def __init__(self):
        self.credentials = self._login_azure_app_token()
        self.subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        self.resource_client = ResourceManagementClient(self.credentials, self.subscription_id)
        self.client = ContainerInstanceManagementClient(self.credentials, self.subscription_id)

    def _login_azure_app_token(self, client_id=None, client_secret=None, tenant_id=None):
        """
        Authenticate APP using token credentials:
        https://docs.microsoft.com/en-us/python/azure/python-sdk-azure-authenticate?view=azure-python
        :return: ~ServicePrincipalCredentials credentials
        """
        client_id = os.getenv('AZURE_CLIENT_ID') if not client_id else client_id
        client_secret = os.getenv('AZURE_CLIENT_SECRET') if not client_secret else client_secret
        tenant_id = os.getenv('AZURE_TENANT_ID') if not tenant_id else tenant_id
        credentials = ServicePrincipalCredentials(
            client_id=client_id,
            secret=client_secret,
            tenant=tenant_id,
        )
        return credentials

    def generate_sasurl(self, url, account_name, account_key, container):
        bs = BlockBlobService(account_name=account_name,
                              account_key=account_key)
        sas_token = bs.generate_blob_shared_access_signature(container,
                                                             url.split('/')[-1],
                                                             permission=BlobPermissions.READ,
                                                             expiry=datetime.utcnow() + timedelta(hours=24),
                                                             )
        source_blob_url = bs.make_blob_url(container, url.split('/')[-1],
                                           sas_token=sas_token)
        return source_blob_url

    def prepare_container(self, asset_url, algorithm_url, docker_image, account_name, account_key):
        """Prepare a docker image that will run in the cloud, mounting the asset and executing the algorithm.
        :param asset_url
        :param algorithm_url
        :param docker_image
        """
        # self.copy('testfiles', 'https://testocnfiles.blob.core.windows.net/testfiles/boston.txt', 'boston', 'boston.txt',
        #      'testocnfiles', 'k2Vk4yfb88WNlWW+W54a8ytJm8MYO1GW9IgiV7TNGKSdmKyVNXzyhiRZ3U1OHRotj/vTYdhJj+ho30HPyJpuYQ==')

        container = self.create_container_group(resource_group_name='OceanProtocol',
                                                name='mycontainer',
                                                image='python:3.6-alpine',
                                                location='eastus',
                                                memory=1,
                                                cpu=1
                                                # azure_file='https://testocnfiles.file.core.windows.net/boston/boston.txt',
                                                # command=None)
                                                )

        return 'gell'

    def copy(self, blob_container, blob_url, file_share, file_name, account_name, account_key):
        fs = FileService(account_name=account_name, account_key=account_key)

        fs.copy_file(file_share,
                     '',
                     file_name,
                     self.generate_sasurl(blob_url, account_name, account_key, blob_container))

    def create_container_group(self,resource_group_name, name, location, image, memory, cpu):
        # setup default values
        port = 80
        container_resource_requirements = None
        command = None
        environment_variables = None

        # set memory and cpu
        container_resource_requests = ResourceRequests(memory_in_gb=memory, cpu=cpu)
        container_resource_requirements = ResourceRequirements(requests=container_resource_requests)

        container = Container(name=name,
                              image=image,
                              resources=container_resource_requirements,
                              command=command,
                              ports=[ContainerPort(port=port)],
                              environment_variables=environment_variables)

        # defaults for container group
        cgroup_os_type = OperatingSystemTypes.linux
        cgroup_ip_address = IpAddress(type='public',
                                      ports=[Port(protocol=ContainerGroupNetworkProtocol.tcp, port=port)])
        image_registry_credentials = None

        cgroup = ContainerGroup(location=location,
                                containers=[container],
                                os_type=cgroup_os_type,
                                ip_address=cgroup_ip_address,
                                image_registry_credentials=image_registry_credentials)

        self.client.container_groups.create_or_update(resource_group_name, name, cgroup)

    def show_container_group(self, resource_group_name, name):
        cgroup = self.client.container_groups.get(resource_group_name, name)

        print('\n{0}\t\t\t{1}\t{2}'.format('name', 'location', 'provisioning state'))
        print('---------------------------------------------------')
        print('{0}\t\t{1}\t\t{2}'.format(cgroup.name, cgroup.location, cgroup.provisioning_state))

    def delete_resources(self, resource_group_name, container_group_name):
        self.client.container_groups.delete(resource_group_name, container_group_name)
        self.resource_client.resource_groups.delete(resource_group_name)


osm = Osmosis()
# osm.show_container_group('OceanProtocol','myapp')
osm.prepare_container('https://testocnfiles.file.core.windows.net/boston/boston.txt', '', '', '', '')

import logging
import os
import time
from datetime import datetime, timedelta

from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.containerinstance import ContainerInstanceManagementClient
from azure.mgmt.containerinstance.models import (ContainerGroup, Container, ResourceRequirements, ResourceRequests,
                                                 OperatingSystemTypes, Volume, VolumeMount, AzureFileVolume,
                                                 ContainerGroupRestartPolicy)
from azure.mgmt.resource import ResourceManagementClient
from azure.storage.blob import BlobPermissions
from azure.storage.blob import BlockBlobService
from azure.storage.file import FileService
from squid_py.config import Config


class Osmosis(object):
    def __init__(self, config_file=None):
        self.credentials = self._login_azure_app_token()
        self.subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
        self.resource_client = ResourceManagementClient(self.credentials, self.subscription_id)
        self.client = ContainerInstanceManagementClient(self.credentials, self.subscription_id)
        self.config = Config(config_file)

    @staticmethod
    def _login_azure_app_token(client_id=None, client_secret=None, tenant_id=None):
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

    @staticmethod
    def generate_sasurl(url, account_name, account_key, container):
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

    def exec_container(self,
                       asset_url,
                       algorithm_url,
                       resource_group_name,
                       account_name,
                       account_key,
                       location,
                       share_name_input='compute',
                       share_name_output='output',
                       docker_image='python:3.6-alpine',
                       memory=1.5,
                       cpu=1):
        """Prepare a docker image that will run in the cloud, mounting the asset and executing the algorithm.
        :param asset_url
        :param algorithm_url
        :param resource_group_name:
        :param account_name:
        :param account_key:
        :param share_name_input:
        :param share_name_output:
        :param location:
        """
        try:
            container_group_name = 'compute' + str(int(time.time()))
            result_file = self._create_container_group(resource_group_name=resource_group_name,
                                                       name=container_group_name,
                                                       image=docker_image,
                                                       location=location,
                                                       memory=memory,
                                                       cpu=cpu,
                                                       algorithm=algorithm_url,
                                                       asset=asset_url,
                                                       input_mount_point='/input',
                                                       output_moint_point='/output',
                                                       account_name=account_name,
                                                       account_key=account_key,
                                                       share_name_input=share_name_input,
                                                       share_name_output=share_name_output
                                                       )
            while self.client.container_groups.get(resource_group_name,
                                                   container_group_name).provisioning_state != 'Succeeded':
                logging.info("Waiting to resources ")
            while self.client.container_groups.get(resource_group_name, container_group_name). \
                    containers[0].instance_view.current_state.state != 'Terminated':
                logging.info("Waiting to terminate")
            self.delete_resources(resource_group_name, container_group_name)
            return result_file
        except Exception:
            logging.error("There was a problem executing your container")
            raise Exception

    def _create_container_group(self, resource_group_name, name, location, image, memory, cpu, algorithm, asset,
                                input_mount_point, output_moint_point, account_name, account_key, share_name_input,
                                share_name_output):
        # setup default values
        result_file = 'result-' + str(int(time.time()))
        command = ['python', input_mount_point + '/' + algorithm, input_mount_point + '/' + asset,
                   output_moint_point + '/' + result_file]
        environment_variables = None
        az_file_input = AzureFileVolume(share_name=share_name_input,
                                        storage_account_name=account_name,
                                        storage_account_key=account_key,
                                        )

        az_file_output = AzureFileVolume(share_name=share_name_output,
                                         storage_account_name=account_name,
                                         storage_account_key=account_key,
                                         )

        volume = [Volume(name=share_name_input, azure_file=az_file_input),
                  Volume(name=share_name_output, azure_file=az_file_output)]
        volume_mount = [VolumeMount(name=share_name_input, mount_path=input_mount_point),
                        VolumeMount(name=share_name_output, mount_path=output_moint_point)]

        # set memory and cpu
        container_resource_requests = ResourceRequests(memory_in_gb=memory, cpu=cpu)
        container_resource_requirements = ResourceRequirements(requests=container_resource_requests)

        container = Container(name=name,
                              image=image,
                              resources=container_resource_requirements,
                              command=command,
                              environment_variables=environment_variables,
                              volume_mounts=volume_mount,
                              )

        # defaults for container group
        cgroup_os_type = OperatingSystemTypes.linux

        cgroup = ContainerGroup(location=location,
                                containers=[container],
                                os_type=cgroup_os_type,
                                restart_policy=ContainerGroupRestartPolicy.never,
                                volumes=volume,
                                )

        self.client.container_groups.create_or_update(resource_group_name, name, cgroup)
        return result_file

    def delete_resources(self, resource_group_name, container_group_name):
        self.client.container_groups.delete(resource_group_name, container_group_name)

    def list_container_groups(self, resource_group_name):
        """Lists the container groups in the specified resource group.

        Arguments:
           aci_client {azure.mgmt.containerinstance.ContainerInstanceManagementClient}
                       -- An authenticated container instance management client.
           resource_group {azure.mgmt.resource.resources.models.ResourceGroup}
                       -- The resource group containing the container group(s).
        """
        print("Listing container groups in resource group '{0}'...".format(resource_group_name))

        container_groups = self.client.container_groups.list_by_resource_group(resource_group_name)

        for container_group in container_groups:
            print("  {0}".format(container_group.name))

    def copy(self, blob_container, blob_url, file_share, file_name, account_name, account_key):
        fs = FileService(account_name=account_name, account_key=account_key)

        fs.copy_file(file_share,
                     '',
                     file_name,
                     self.generate_sasurl(blob_url, account_name, account_key, blob_container))

    @classmethod
    def create_file_share(cls, share_name, file_name, account_name, local_file, account_key,
                          directory_name='output'):
        fs = FileService(account_name=account_name, account_key=account_key)
        fs.create_file_from_path(share_name, directory_name, file_name, local_file_path=local_file)

    @classmethod
    def list_file_shares(cls, account_name, account_key, share_name):
        fs = FileService(account_name=account_name, account_key=account_key)
        return fs.list_directories_and_files(share_name).items

    @classmethod
    def delete_file_share(cls, account_name, account_key, share_name, file_name, directory_name=''):
        fs = FileService(account_name=account_name, account_key=account_key)
        return fs.delete_file(share_name, directory_name, file_name)

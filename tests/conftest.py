import os

import pytest
from squid_py.ocean.account import Account
from squid_py.ocean.ocean import Ocean

from brizo.run import app

app = app


@pytest.fixture
def client():
    client = app.test_client()
    yield client

json_brizo = {
    "consumer_wallet": "",
    "algorithm_did": "algo.py",
    "asset_did": "data.txt",
    "docker_image": "python:3.6-alpine",
    "memory": 1.5,
    "cpu": 1
}


@pytest.fixture
def sla_template():
    return

@pytest.fixture
def publisher_ocean_instance():
    return get_publisher_ocean_instance()


@pytest.fixture
def consumer_ocean_instance():
    return get_consumer_ocean_instance()


def init_ocn_tokens(ocn, amount=100):
    ocn.keeper.market.unlock_account(ocn.main_account)
    ocn.keeper.market.contract_concise.requestTokens(amount, transact={'from': ocn.main_account.address})
    ocn.keeper.market.unlock_account(ocn.main_account)
    ocn.keeper.token.contract_concise.approve(
        ocn.keeper.payment_conditions.address,
        amount,
        transact={'from': ocn.main_account.address},
    )


def make_ocean_instance(secret_store_client, account_index):
    path_config = 'config_local.ini'
    os.environ['CONFIG_FILE'] = path_config
    ocn = Ocean(os.environ['CONFIG_FILE'], secret_store_client=secret_store_client)
    ocn.main_account = Account(ocn.keeper, list(ocn.accounts)[account_index])
    return ocn


def get_publisher_ocean_instance():
    ocn = make_ocean_instance(None, 0)
    address = None
    if ocn.config.has_option('keeper-contracts', 'parity.address'):
        address = ocn.config.get('keeper-contracts', 'parity.address')
    address = ocn.keeper.web3.toChecksumAddress(address) if address else None
    if address and address in ocn.accounts:
        password = ocn.config.get('keeper-contracts', 'parity.password') \
            if ocn.config.has_option('keeper-contracts', 'parity.password') else None
        ocn.set_main_account(address, password)
    init_ocn_tokens(ocn)
    return ocn


def get_consumer_ocean_instance():
    ocn = make_ocean_instance(None, 0)
    address = None
    if ocn.config.has_option('keeper-contracts', 'parity.address1'):
        address = ocn.config.get('keeper-contracts', 'parity.address1')

    address = ocn.keeper.web3.toChecksumAddress(address) if address else None
    if address and address in ocn.accounts:
        password = ocn.config.get('keeper-contracts', 'parity.password1') \
            if ocn.config.has_option('keeper-contracts', 'parity.password1') else None
        ocn.set_main_account(address, password)
    init_ocn_tokens(ocn)
    return ocn


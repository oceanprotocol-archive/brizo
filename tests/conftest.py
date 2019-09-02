#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

import pytest
from ocean_keeper.contract_handler import ContractHandler
from ocean_keeper.utils import get_account
from ocean_keeper.web3_provider import Web3Provider

from brizo.run import app
from brizo.util import get_config, get_keeper_path, init_account_envvars

app = app


@pytest.fixture
def client():
    client = app.test_client()
    yield client


@pytest.fixture(autouse=True)
def setup_all():
    config = get_config()
    Web3Provider.get_web3(config.keeper_url)
    ContractHandler.artifacts_path = get_keeper_path(config)
    init_account_envvars()


def get_publisher_account():
    return get_account(0)


def get_consumer_account():
    return get_account(0)

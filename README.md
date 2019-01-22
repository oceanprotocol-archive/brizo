[![banner](https://raw.githubusercontent.com/oceanprotocol/art/master/github/repo-banner%402x.png)](https://oceanprotocol.com)

# Brizo

> Helping to Publishers to expose their services.
> [oceanprotocol.com](https://oceanprotocol.com)

___"🏄‍♀️🌊 Brizo is an ancient Greek goddess who was known as the protector of mariners, sailors, and fishermen.
She was worshipped primarily by the women of Delos, who set out food offerings in small boats. Brizo was also known as a prophet specializing in the interpretation of dreams."___

[![Docker Build Status](https://img.shields.io/docker/build/oceanprotocol/brizo.svg)](https://hub.docker.com/r/oceanprotocol/brizo/)
[![Travis (.com)](https://img.shields.io/travis/com/oceanprotocol/brizo.svg)](https://travis-ci.com/oceanprotocol/brizo)
[![Codacy coverage](https://img.shields.io/codacy/coverage/40dd4c27169a4db4865f72317172bd9e.svg)](https://app.codacy.com/project/ocean-protocol/brizo/dashboard)
[![PyPI](https://img.shields.io/pypi/v/ocean-brizo.svg)](https://pypi.org/project/ocean-brizo/)
[![GitHub contributors](https://img.shields.io/github/contributors/oceanprotocol/brizo.svg)](https://github.com/oceanprotocol/brizo/graphs/contributors)

---

**🐲🦑 THERE BE DRAGONS AND SQUIDS. This is in alpha state and you can expect running into problems. If you run into them, please open up [a new issue](https://github.com/oceanprotocol/brizo/issues). 🦑🐲**

---

## Table of Contents

  - [Features](#features)
  - [Running Locally, for Dev and Test](#running-locally-for-dev-and-test)
  - [API documentation](#api-documentation)
  - [Configuration](#configuration)
  - [Dependencies](#dependencies)
  - [Code style](#code-style)
  - [Testing](#testing)
  - [Debugging](#debugging)
  - [New Version](#new-version)
  - [License](#license)

---

## Features

In the "Ocean ecosystem", Brizo is the technical component executed by the Publishers allowing to them to provide extended data services. Brizo, as part of the Publisher ecosystem, includes the credentials to interact with the infrastructure (initially cloud, but could be on-premise).

## Running Locally, for Dev and Test

If you want to contribute to the development of Brizo, then you could do the following. (If you want to run a Brizo in production, then you will have to do something else.)

First, clone this repository:

```bash
git clone git@github.com:oceanprotocol/brizo.git
cd brizo/
```

Then run some things that Brizo expects to be running:

```bash
git clone git@github.com:oceanprotocol/barge.git
cd barge
bash start_ocean.sh --no-brizo --no-pleuston --local-spree-node
```

Barge is the repository where all the docker-compose are allocated. We are running the script start_ocean that is the easy way to have ocean projects up and running.
We are selecting run without the brizo and pleuston instance. 

To know more about visit [Barge](https://github.com/oceanprotocol/barge)

Note that it runs a Aquarius instance and MongoDB but the Aquarius can also work with BigchainDB or Elasticsearch.

The most simple way to start is:

```bash
pip install -r requirements_dev.txt
export FLASK_APP=brizo/run.py
export CONFIG_FILE=config.ini
./scripts/wait_for_migration_and_extract_keeper_artifacts.sh
flask run
```

That will use HTTP (i.e. not SSL/TLS).

The proper way to run the Flask application is using an application server such as Gunicorn. This allow you to run using SSL/TLS.
You can generate some certificates for testing by doing:

```bash
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
```

and when it asks for the Common Name (CN), answer `localhost`

Then edit the config file `config.ini` so that:

```yaml
brizo.url = https://localhost:8030
```

Then execute this command:

```bash
gunicorn --certfile cert.pem --keyfile key.pem -b 0.0.0.0:8030 -w 1 brizo.run:app
```

## API documentation

Once you have your application running you can get access to the documentation at:

```bash
https://127.0.0.1:8030/api/v1/docs
```

Currently Brizo gives you the possibility of serving your data allocated in an Azure BlobStorage and a basic capability of execution of an algorithm.

## Configuration

You can pass the configuration using the CONFIG_FILE environment variable (recommended) or locating your configuration in config.ini file.

In the configuration there are now three sections:

- keeper-contracts: This section help you to connect with the network where you have deployed the contracts. You can find more information of how to configure [here](https://github.com/oceanprotocol/squid-py#quick-start).

    ```yaml
    [keeper-contracts]
    keeper.url = http://127.0.0.1:8545
    ```

- resources: This section is necessary for the squid-py library.

    ```yaml
    [resources]
    ;; brizo url (optional) is used mainly in development and testing
    brizo.url = http://localhost:8030
    ;; path to database file where all access requests are stored
    storage.path = squid_py.db
    ```

- osmosis: Specify the cloud storage and compute account credentials to allow generating signed urls and enable executing algorithms. We are assuming that the algorithm and the data are in the same folder for this first approach.

    ```yaml
    [osmosis]
    azure.account.name = <Azure Storage Account Name (for storing files)>
    azure.account.key = <Azure Storage Account key>
    azure.resource_group = <Azure resource group>
    azure.location = <Azure Region>
    azure.client.id = <Azure Application ID>
    azure.client.secret = <Azure Application Secret>
    azure.tenant.id = <Azure Tentant ID>
    azure.subscription.id = <Azure Subscription>
    azure.share.input = compute
    azure.share.output = output
    ```

Also, when running in container or locally, environment variables can be used to configure the azure credentials. These are the variables needed to export:

```text
AZURE_ACCOUNT_NAME: Azure Storage Account Name (for storing files)
AZURE_ACCOUNT_KEY: Azure Storage Account key
AZURE_RESOURCE_GROUP: Azure resource group
AZURE_LOCATION: Azure Region
AZURE_CLIENT_ID: Azure Application ID
AZURE_CLIENT_SECRET: Azure Application Secret
AZURE_TENANT_ID: Azure Tenant ID
AZURE_SUBSCRIPTION_ID: Azure Subscription
```

## Dependencies

Brizo relies on the following `Ocean` libraries:

- squid-py: `https://github.com/oceanprotocol/squid-py` -- handles all of the `keeper` interactions
- osmosis-azure-driver: `https://github.com/oceanprotocol/osmosis-azure-driver` -- simplifies access to azure cloud services

## Code style

The information about code style in python is documented in this two links [python-developer-guide](https://github.com/oceanprotocol/dev-ocean/blob/master/doc/development/python-developer-guide.md)
and [python-style-guide](https://github.com/oceanprotocol/dev-ocean/blob/master/doc/development/python-style-guide.md).

## Testing

Automatic tests are setup via Travis, executing `tox`.
Our test use pytest framework.

## Debugging

To debug Brizo using PyCharm, follow the next instructions:

1. Clone [barge](https://github.com/oceanprotocol/barge) repository.
2. Run barge omitting `brizo`. (i.e.:`bash start_ocean.sh --no-brizo --no-pleuston --local-nile-node`)
3. In PyCharm, go to _Settings > Project Settings > Python Debugger_, and select the option _Gevent Compatible_
4. Configure a new debugger configuration: _Run > Edit Configurations..._, there click on _Add New Configuration_
5. Configure as shown in the next image:
![Pycharm Debugger configuration](imgs/debugger_configuration.png)
6. Setup the next environment variables:
```
PYTHONUNBUFFERED=1
CONFIG_FILE=config_dev.ini
AZURE_ACCOUNT_NAME=<COMPLETE_WITH_YOUR_DATA>
AZURE_TENANT_ID=<COMPLETE_WITH_YOUR_DATA>
AZURE_SUBSCRIPTION_ID=<COMPLETE_WITH_YOUR_DATA>
AZURE_LOCATION=<COMPLETE_WITH_YOUR_DATA>
AZURE_CLIENT_SECRET=<COMPLETE_WITH_YOUR_DATA>
AZURE_CLIENT_ID=<COMPLETE_WITH_YOUR_DATA>
AZURE_ACCOUNT_KEY=<COMPLETE_WITH_YOUR_DATA>
AZURE_RESOURCE_GROUP=<COMPLETE_WITH_YOUR_DATA>
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
```
The option `OBJC_DISABLE_INITIALIZE_FORK_SAFETY` is needed if you run in last versions of MacOS.
7. Now you can configure your breakpoints and debug brizo or squid-py.


## New Version

The `bumpversion.sh` script helps to bump the project version. You can execute the script using as first argument {major|minor|patch} to bump accordingly the version.

## License

```text
Copyright 2018 Ocean Protocol Foundation Ltd.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

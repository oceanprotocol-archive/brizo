[![banner](https://raw.githubusercontent.com/oceanprotocol/art/master/github/repo-banner%402x.png)](https://oceanprotocol.com)

# Brizo

> Helping to Publishers to expose their services.
> [oceanprotocol.com](https://oceanprotocol.com)

___"Brizo is an ancient Greek goddess who was known as the protector of mariners, sailors, and fishermen. 
She was worshipped primarily by the women of Delos, who set out food offerings in small boats. Brizo was also known as a prophet specializing in the interpretation of dreams."___

[![Docker Build Status](https://img.shields.io/docker/build/oceanprotocol/brizo.svg)](https://hub.docker.com/r/oceanprotocol/brizo/) 
[![Travis (.com)](https://img.shields.io/travis/com/oceanprotocol/brizo.svg)](https://travis-ci.com/oceanprotocol/brizo)
[![Codacy coverage](https://img.shields.io/codacy/coverage/0fa4c47049434406ad80932712f7ee6f.svg)](https://app.codacy.com/project/ocean-protocol/brizo/dashboard) 
[![PyPI](https://img.shields.io/pypi/v/ocean-brizo.svg)](https://pypi.org/project/ocean-brizo/) 
[![GitHub contributors](https://img.shields.io/github/contributors/oceanprotocol/brizo.svg)](https://github.com/oceanprotocol/brizo/graphs/contributors)

---

## Table of Contents

  - [Code style](#code-style)
  - [Testing](#testing)
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
cd docker
docker-compose up
```

You can see what that runs by reading [docker/docker-compose.yml](docker/docker-compose.yml).
Note that it runs a Provider instance and MongoDB but the Provider can also work with BigchainDB or Elasticsearch.
It also runs [Ganache](https://github.com/trufflesuite/ganache) with all [Ocean Protocol Keeper Contracts](https://github.com/oceanprotocol/keeper-contracts) and [Ganache CLI](https://github.com/trufflesuite/ganache-cli).

The most simple way to start is:

```bash
pip install -r requirements_dev.txt # or requirements_conda.txt if using Conda
export FLASK_APP=brizo/run.py
export CONFIG_FILE=config.ini
./scripts/deploy
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

Currently Brizo give you the posibility of consume your data allocated in an Azure BlobStorage and a basic capability of execution of an algorithm.

## Configuration

You can pass the configuration using the CONFIG_FILE environment variable (recommended) or locating your configuration in config.ini file.

In the configuration there are now two sections:

- keeper-contracts: This section help you to connect with the network where you have deployed the contracts. You can find more information of how to configure [here](https://github.com/oceanprotocol/squid-py#quick-start).
    ```yaml
    [keeper-contracts]
    keeper.url = http://127.0.0.1:8545
    keeper.network = development
    
    ;contracts.folder=venv/contracts
    market.address =
    auth.address =
    token.address =
    provider.address =
    provider.account =
    ```
- resources: In this section we are showing the url in wich the provider is going to be deployed.

    ```yaml
    [resources]
    azure.account.name = testocnfiles
    azure.account.key = DCNmb542DWbtkPf1lKz+WXii6Z50vScBvVJQMOy4XtG+bVIjHymbKm8iUZnSdlQlLRsrxlWaOwvAzbQmSm/oBw==
    azure.container = testfiles
    azure.resource_group = OceanProtocol
    azure.share.input = compute
    azure.share.output = output
    azure.location = westus
    
    ;; These consitute part of the provider url which is used in setting the `api_url` in the `OceanContractsWrapper`
    provider.url = http://localhost:5000
    brizo.url = http://localhost:8030
    ```


## Code style

The information about code style in python is documented in this two links [python-developer-guide](https://github.com/oceanprotocol/dev-ocean/blob/master/doc/development/python-developer-guide.md)
and [python-style-guide](https://github.com/oceanprotocol/dev-ocean/blob/master/doc/development/python-style-guide.md).
    
## Testing

Automatic tests are setup via Travis, executing `tox`.
Our test use pytest framework.

## New Version

The `bumpversion.sh` script helps to bump the project version. You can execute the script using as first argument {major|minor|patch} to bump accordingly the version.

## License

```
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



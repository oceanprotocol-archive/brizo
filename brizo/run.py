#  Copyright 2018 Ocean Protocol Foundation
#  SPDX-License-Identifier: Apache-2.0

import configparser

from flask import jsonify
from flask_swagger import swagger
from flask_swagger_ui import get_swaggerui_blueprint
from squid_py.config import Config
from squid_py.keeper import Keeper

from brizo.constants import BaseURLs, ConfigSections, Metadata
from brizo.myapp import app
from brizo.routes import services


def get_version():
    conf = configparser.ConfigParser()
    conf.read('.bumpversion.cfg')
    return conf['bumpversion']['current_version']


@app.route("/")
def version():
    keeper = Keeper.get_instance()
    info = dict()
    info['software'] = Metadata.TITLE
    info['version'] = get_version()
    info['keeper-url'] = config.get('keeper-contracts', 'keeper.url')
    info['network'] = keeper.get_instance().network_name
    info['contracts'] = dict()
    info['contracts']['AccessSecretStoreCondition'] = keeper.get_instance().access_secret_store_condition.address
    info['contracts']['AgreementStoreManager'] = keeper.get_instance().agreement_manager.address
    info['contracts']['ConditionStoreManager'] = keeper.get_instance().condition_manager.address
    info['contracts']['DIDRegistry'] = keeper.get_instance().did_registry.address
    if keeper.get_instance().network_name != 'pacific':
        info['contracts']['Dispenser'] = keeper.get_instance().dispenser.address
    info['contracts']['EscrowAccessSecretStoreTemplate'] = keeper.get_instance().escrow_access_secretstore_template.address
    info['contracts']['EscrowReward'] = keeper.get_instance().escrow_reward_condition.address
    info['contracts']['HashLockCondition'] = keeper.get_instance().hash_lock_condition.address
    info['contracts']['LockRewardCondition'] = keeper.get_instance().lock_reward_condition.address
    info['contracts']['SignCondition'] = keeper.get_instance().sign_condition.address
    info['contracts']['OceanToken'] = keeper.get_instance().token.address
    info['contracts']['TemplateStoreManager'] = keeper.get_instance().template_manager.address
    info['keeper-version'] = keeper.get_instance().token.version
    return jsonify(info)


@app.route("/spec")
def spec():
    swag = swagger(app)
    swag['info']['version'] = get_version()
    swag['info']['title'] = Metadata.TITLE
    swag['info']['description'] = Metadata.DESCRIPTION
    return jsonify(swag)


config = Config(filename=app.config['CONFIG_FILE'])
brizo_url = config.get(ConfigSections.RESOURCES, 'brizo.url')
# Call factory function to create our blueprint
swaggerui_blueprint = get_swaggerui_blueprint(
    BaseURLs.SWAGGER_URL,
    brizo_url + '/spec',
    config={  # Swagger UI config overrides
        'app_name': "Test application"
    },
)

# Register blueprint at URL
app.register_blueprint(swaggerui_blueprint, url_prefix=BaseURLs.SWAGGER_URL)
app.register_blueprint(services, url_prefix=BaseURLs.ASSETS_URL)

if __name__ == '__main__':
    app.run(port=8030)

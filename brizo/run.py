from flask import jsonify
from flask_swagger import swagger
from flask_swagger_ui import get_swaggerui_blueprint
from squid_py.config import Config

from brizo.constants import BaseURLs
from brizo.myapp import app
from brizo.routes import services


@app.route("/spec")
def spec():
    swag = swagger(app)
    swag['info']['version'] = "1.0"
    swag['info']['title'] = "Ocean-provider"
    return jsonify(swag)


config = Config(filename=app.config['CONFIG_FILE'])
provider_url = config.provider_url
# Call factory function to create our blueprint
swaggerui_blueprint = get_swaggerui_blueprint(
    BaseURLs.SWAGGER_URL,
    provider_url + '/spec',
    config={  # Swagger UI config overrides
        'app_name': "Test application"
    },
)

# Register blueprint at URL
app.register_blueprint(swaggerui_blueprint, url_prefix=BaseURLs.SWAGGER_URL)
app.register_blueprint(services, url_prefix=BaseURLs.ASSETS_URL)

if __name__ == '__main__':
    app.run(port=8080)

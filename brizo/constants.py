class ConfigSections:
    KEEPER_CONTRACTS = 'keeper-contracts'
    RESOURCES = 'resources'
    OSMOSIS = 'osmosis'


class BaseURLs:
    BASE_BRIZO_URL = '/api/v1/brizo'
    SWAGGER_URL = '/api/v1/docs'  # URL for exposing Swagger UI (without trailing '/')
    ASSETS_URL = BASE_BRIZO_URL + '/services'

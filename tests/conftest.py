import pytest

from brizo.run import app

app = app


@pytest.fixture
def client():
    client = app.test_client()
    yield client


json_dict = {
  "@context": "https://w3id.org/future-method/v1",
  "id": "did:op:123456789abcdefghi",
  "publicKey": [
    {
      "id": "did:op:123456789abcdefghi#keys-1",
      "type": "RsaVerificationKey2018",
      "owner": "did:op:123456789abcdefghi",
      "publicKeyPem": "-----BEGIN PUBLIC KEY...END PUBLIC KEY-----\r\n"
    },
    {
      "id": "did:op:123456789abcdefghi#keys-2",
      "type": "Ed25519VerificationKey2018",
      "owner": "did:op:123456789abcdefghi",
      "publicKeyBase58": "H3C2AVvLMv6gmMNam3uVAjZpfkcJCwDwnZn6z3wXmqPV"
    },
    {
      "id": "did:op:123456789abcdefghi#keys-3",
      "type": "RsaPublicKeyExchangeKey2018",
      "owner": "did:op:123456789abcdefghi",
      "publicKeyPem": "-----BEGIN PUBLIC KEY...END PUBLIC KEY-----\r\n"
    }
  ],
  "authentication": [
    {
      "type": "RsaSignatureAuthentication2018",
      "publicKey": "did:op:123456789abcdefghi#keys-1"
    },
    {
      "type": "ieee2410Authentication2018",
      "publicKey": "did:op:123456789abcdefghi#keys-2"
    }
  ],
  "service": [
    {
      "id": "did:op:123456789abcdefghi",
      "type": "OpenIdConnectVersion1.0Service",
      "serviceEndpoint": "https://openid.example.com/"
    },
    {
      "id": "did:op:123456789abcdefghi",
      "type": "CredentialRepositoryService",
      "serviceEndpoint": "https://repository.example.com/service/8377464"
    },
    {
      "id": "did:op:123456789abcdefghi",
      "type": "XdiService",
      "serviceEndpoint": "https://xdi.example.com/8377464"
    },
    {
      "id": "did:op:123456789abcdefghi",
      "type": "HubService",
      "serviceEndpoint": "https://hub.example.com/.identity/did:op:0123456789abcdef/"
    },
    {
      "id": "did:op:123456789abcdefghi",
      "type": "MessagingService",
      "serviceEndpoint": "https://example.com/messages/8377464"
    },
    {
      "id": "did:op:123456789abcdefghi",
      "type": "SocialWebInboxService",
      "serviceEndpoint": "https://social.example.com/83hfh37dj",
      "description": "My public social inbox",
      "spamCost": {
        "amount": "0.50",
        "currency": "USD"
      }
    },
    {
      "id": "did:op:123456789abcdefghi;bops",
      "type": "BopsService",
      "serviceEndpoint": "https://bops.example.com/enterprise/"
    },
    {
      "id": "did:op:123456789abcdefghi",
      "type": "Consume",
      "serviceEndpoint": "http://mybrizo.org/api/v1/brizo/services/consume?pubKey=${pubKey}&serviceId={serviceId}&url={url}"
    },
    {
      "id": "did:op:123456789abcdefghi",
      "type": "Compute",
      "serviceEndpoint": "http://mybrizo.org/api/v1/brizo/services/compute?pubKey=${pubKey}&serviceId={serviceId}&algo={algo}&container={container}"
    },
    {
      "id": "did:op:123456789abcdefghi",
      "type": "Metadata",
      "serviceEndpoint": "http://myaquarius.org/api/v1/provider/assets/metadata/{did}",
      "metadata": {
        "base": {
          "name": "UK Weather information 2011",
          "type": "dataset",
          "description": "Weather information of UK including temperature and humidity",
          "size": "3.1gb",
          "dateCreated": "2012-10-10T17:00:000Z",
          "author": "Met Office",
          "license": "CC-BY",
          "copyrightHolder": "Met Office",
          "encoding": "UTF-8",
          "compression": "zip",
          "contentType": "text/csv",
          "workExample": "423432fsd,51.509865,-0.118092,2011-01-01T10:55:11+00:00,7.2,68",
          "contentUrls": [
            "https://testocnfiles.blob.core.windows.net/testfiles/testzkp.pdf"
          ],
          "links": [
            { "name": "Sample of Asset Data", "type": "sample", "url": "https://foo.com/sample.csv" },
            { "name": "Data Format Definition", "type": "format", "AssetID": "4d517500da0acb0d65a716f61330969334630363ce4a6a9d39691026ac7908ea" }
          ],
          "inLanguage": "en",
          "tags": "weather, uk, 2011, temperature, humidity",
          "price": 10
        },
        "curation": {
          "rating": 0.93,
          "numVotes": 123,
          "schema": "Binary Voting"
        },
        "additionalInformation": {
          "updateFrequency": "yearly",
          "structuredMarkup": [
            {
              "uri": "http://skos.um.es/unescothes/C01194/jsonld",
              "mediaType": "application/ld+json"
            },
            {
              "uri": "http://skos.um.es/unescothes/C01194/turtle",
              "mediaType": "text/turtle"
            }
          ]
        }
      }
    }
  ]
}
json_request_consume = {
    'requestId': "",
    'consumerId': "",
    'fixed_msg': "",
    'sigEncJWT': ""
}

json_brizo = {
    "consumer_wallet": "",
    "algorithm_did": "algo.py",
    "asset_did": "data.txt",
    "docker_image": "python:3.6-alpine",
    "memory": 1.5,
    "cpu": 1
}

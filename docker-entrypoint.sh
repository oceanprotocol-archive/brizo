#!/bin/sh

export CONFIG_FILE=/brizo/oceandb.ini
envsubst < /brizo/oceandb.ini.template > /brizo/oceandb.ini
if [ "${LOCAL_CONTRACTS}" = "true" ]; then
  echo "Waiting for contracts to be generated..."
  while [ ! -f "/usr/local/keeper-contracts/ready" ]; do
    sleep 2
  done
fi
market=$(python -c "import sys, json; print(json.load(open('/usr/local/keeper-contracts/OceanMarket.development.json', 'r'))['address'])")
token=$(python -c "import sys, json; print(json.load(open('/usr/local/keeper-contracts/OceanToken.development.json', 'r'))['address'])")
auth=$(python -c "import sys, json; print(json.load(open('/usr/local/keeper-contracts/OceanAuth.development.json', 'r'))['address'])")
sed -i -e "/token.address =/c token.address = ${token}" /brizo/oceandb.ini
sed -i -e "/market.address =/c market.address = ${market}" /brizo/oceandb.ini
sed -i -e "/auth.address =/c auth.address = ${auth}" /brizo/oceandb.ini
gunicorn -b ${BRIZO_HOST}:${BRIZO_PORT} -w ${BRIZO_WORKERS} brizo.run:app
tail -f /dev/null

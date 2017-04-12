#!/usr/bin/bash -ex

gc() {
  retval=$?
  sudo docker-compose -f local-setup/docker-compose.yaml down -v || :
  exit $retval
}
trap gc EXIT SIGINT

# Enter local-setup/ directory
# Run local instances for: dynamodb, gremlin-websocket, gremlin-http
function start_gremlin_http_websocket {
    pushd local-setup/
    echo "Invoke Docker Compose Start Gremlin HTTP and WebSocket services"
    sudo docker-compose -f docker-compose.yaml up --force-recreate -d gremlin-websocket gremlin-http
    popd
}


echo JAVA_OPTIONS value: $JAVA_OPTIONS

start_gremlin_http_websocket

export LOGFILE_PATH="all-tests.log"
rm -f "$LOGFILE_PATH"

export PYTHONPATH=`pwd`/src

# rm -rf env-test/
echo "Create Virtualenv for Python deps ..."
virtualenv --python /usr/bin/python2.7 env-test
source env-test/bin/activate

pip install -r requirements.txt

# Install profiling module
pip install pytest-profiling

echo "Create a default configuration file..."
cp src/config.py.template src/config.py

# Wait for services to be up
echo "Wait for some time delay..."
sleep 20

# Check for sanity of the connections
python src/sanitycheck.py || exit -1

# py.test --profile-svg -s test/

py.test -s test/

# Print all the logs for inspection

cat $LOGFILE_PATH

rm -rf env-test/


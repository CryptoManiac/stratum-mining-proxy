#!/bin/bash
set -e

# stratum-proxy auto-install

# Must be root
if [[ `whoami` != 'root' ]]
then
  echo 'You must be root to continue the installation'
  exit 1
fi

# Only works on debian systems
if [[ ! -f '/etc/debian_version' ]]
then
  echo 'Auto-install is for debian/ubuntu only'
  exit 1
fi

# Python development package is required
sudo apt-get install -y git-core python-dev
git clone https://github.com/CryptoManiac/stratum-mining-proxy.git

# This will upgrade setuptools package
cd stratum-mining-proxy
sudo python distribute_setup.py

# Build and install LTC scrypt extension
cd litecoin_scrypt
sudo python setup.py install
cd ..

# This will install required dependencies (namely Twisted and Stratum libraries), but don't install the package into the system.
sudo python setup.py develop

cat <<'FINISHED'
Installation successful!

To begin mining, simply type in:

   ./mining_proxy.py -pa scrypt -o <your pool> -p 3333

And then connect your miners to this host on port 8332.
FINISHED

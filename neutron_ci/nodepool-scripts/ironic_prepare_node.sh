#!/usr/bin/env bash

/opt/nodepool-scripts/ironic_netconfig.sh
/opt/nodepool-scripts/prepare_node.sh

# Install ImcSdk requirement
sudo -H pip install ImcSdk
sudo -H pip install "UcsSdk==0.8.2.2"

# Ensure everything is written to disk
sync

echo "Installed Python Packages:"
sudo -H pip freeze

echo "Ironic Node Prepare Complete!"

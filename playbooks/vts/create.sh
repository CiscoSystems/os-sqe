#!/usr/bin/env bash

venv_dir=vts-venv
source ${venv_dir}/bin/activate

ansible-playbook -i inventory create.yaml
deactivate
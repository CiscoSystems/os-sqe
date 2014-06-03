.DEFAULT_GOAL := init
VENV=.env
CYAN=$(shell echo `tput bold``tput setaf 6`)
RED=$(shell echo `tput bold``tput setaf 1`)
RESET=$(shell echo `tput sgr0`)
#WORKSPACE=$(shell echo ${WORKSPACE})

clean:
	@echo "$(CYAN)>>> Cleaning...$(RESET)"
	deactivate || :
	rm -rf $(VENV) .coverage || :
	find . -name '*.pyc' | xargs rm || :
	find . -name '*~' | xargs rm || :

venv:
	@echo "$(CYAN)>>>> Creating virtualenv...$(RESET)"
	test -d $(VENV) || virtualenv --setuptools $(VENV)

requirements: venv
	@echo "$(CYAN)>>>> Installing dependencies...$(RESET)"
	test $(VENV)/requirements_packages_installed -nt requirements_packages || sudo apt-get install -y `cat requirements_packages` || :
	test $(VENV)/requirements_installed -nt requirements || (. $(VENV)/bin/activate; pip install -Ur requirements && echo > $(VENV)/requirements_installed) || :

init: venv requirements

aio: init prepare-aio install-aio

flake8: init
	@echo "$(CYAN)>>>> Running static analysis...$(RESET)"
	@. $(VENV)/bin/activate; flake8 --max-line-length=120 --show-source --exclude=.env . | \
	awk '{ print } END { if (NR) exit 1}'

flake8-mild:
	@echo "$(CYAN)>>>> Running static analysis...$(RESET)"
	@. $(VENV)/bin/activate; flake8 --max-line-length=120 --show-source --exclude=.env . || echo

help:
	@echo "List of available targets:"
	@make -qp | awk -F ':' '/^[a-zA-Z0-9][^$$#\/\t=]*:([^=]|$$)/ {split($$1,A,/ /); for(i in A) printf " %s\n", A[i]}'| grep -v Makefile | sort

prepare-aio:
	@echo "$(CYAN)>>>> Preparing AIO box...$(RESET)"
	./tools/libvirt-scripts/create.py -u root -a localhost -b cloudimg -l ${LAB} -d /opt/imgs -z ./trusty-server-cloudimg-amd64-disk1.img -o > config_file

prepare-aio-local:
	@echo "$(CYAN)>>>> Preparing AIO box...$(RESET)"
	./tools/libvirt-scripts/create.py -u root -a localhost -b cloudimg -l lab1 -d /media/hdd/tmpdir/tmp/imgs -z /media/hdd/tmpdir/trusty-server-cloudimg-amd64-disk1.img -o > config_file

install-aio:
	@echo "$(CYAN)>>>> Installing AIO...$(RESET)"
	sleep 60
	./tools/deployers/install_aio_coi.py -c config_file

prepare-tempest:
	@echo "$(CYAN)>>>> Preparing tempest...$(RESET)"
	python ${WORKSPACE}/tempest/tools/install_venv.py
	${WORKSPACE}/tempest/.venv/bin/pip install junitxml python-ceilometerclient nose testresources testtools
	. ${WORKSPACE}/tempest/.venv/bin/activate
	./tools/tempest-scripts/tempest_unconfig.sh
	./tools/tempest-scripts/tempest_configurator.sh
	./tools/tempest-scripts/config_creator.sh $$(grep OS_AUTH_URL ./openrc | grep -Eo "/.*:" | sed "s@/@@g"  | sed "s@:@@g")
	mv ./tempest.conf.jenkins ${WORKSPACE}/tempest/etc/tempest.conf

run-tests:
	@echo "$(CYAN)>>>> Run tempest tests ...$(RESET)"
	/bin/bash ./tools/tempest-scripts/run_tempest_tests.sh

run-tempest: prepare-tempest run-tests

full-aio: aio run-tempest

test-me:
	@echo "$(CYAN)>>>> test your commands :) ...$(RESET)"
	echo ${LAB}
	echo $$(grep OS_AUTH_URL ./openrc | grep -Eo "/.*:" | sed "s@/@@g"  | sed "s@:@@g")

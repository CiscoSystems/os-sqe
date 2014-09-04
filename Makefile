.DEFAULT_GOAL := init
VENV=.env
PYTHON=$(VENV)/bin/python
CYAN=$(shell echo `tput bold``tput setaf 6`)
RED=$(shell echo `tput bold``tput setaf 1`)
RESET=$(shell echo `tput sgr0`)
#WORKSPACE=$(shell echo ${WORKSPACE})
UBUNTU_DISK=http://172.29.173.233/trusty-server-cloudimg-amd64-disk1.img
#UBUNTU_DISK=http://cloud-images.ubuntu.com/trusty/current/trusty-server-cloudimg-amd64-disk1.img
ifndef LAB
	LAB="lab1"
endif
ifndef QA_WAITTIME
	QA_WAITTIME=18000
endif
ifndef QA_KILLTIME
	QA_KILLTIME=18060
endif
ifndef WORKSPACE
	WORKSPACE=$$(pwd)"/.."
endif
TPATH=$(WORKSPACE)"/tempest/.venv/bin"

clean:
	@echo "$(CYAN)>>> Cleaning...$(RESET)"
	deactivate || :
	rm -rf $(VENV) .coverage || :
	find . -name '*.pyc' | xargs rm || :
	find . -name '*~' | xargs rm || :

venv:
	@echo "$(CYAN)>>>> Creating virtualenv for LAB=${LAB}...$(RESET)"
	test $(VENV)/requirements_packages_installed -nt requirements_packages || sudo apt-get install -y `cat requirements_packages` || :
	test -d $(VENV) || virtualenv --setuptools $(VENV)

requirements: venv
	@echo "$(CYAN)>>>> Installing dependencies...$(RESET)"
	test $(VENV)/requirements_installed -nt requirements || (. $(VENV)/bin/activate; pip install -Ur requirements && echo > $(VENV)/requirements_installed) || :

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
	test -e trusty-server-cloudimg-amd64-disk1.img || wget -nv $(UBUNTU_DISK)
	time $(PYTHON) ./tools/cloud/create.py -l ${LAB} -s /opt/imgs -z ./trusty-server-cloudimg-amd64-disk1.img -t aio > config_file

prepare-aio-local:
	@echo "$(CYAN)>>>> Preparing AIO box...$(RESET)"
	time ./tools/cloud/create.py -l lab1 -s /media/hdd/tmpdir/tmp/imgs -z /media/hdd/tmpdir/trusty-server-cloudimg-amd64-disk1.img -t aio > config_file

prepare-devstack:
	@echo "$(CYAN)>>>> Preparing AIO box...$(RESET)"
	test -e trusty-server-cloudimg-amd64-disk1.img || wget -nv $(UBUNTU_DISK)
	time $(PYTHON) ./tools/cloud/create.py -l ${LAB} -s /opt/imgs -z ./trusty-server-cloudimg-amd64-disk1.img -t devstack > config_file

prepare-2role:
	@echo "$(CYAN)>>>> Preparing 2_role boxes...$(RESET)"
	test -e trusty-server-cloudimg-amd64-disk1.img || wget -nv $(UBUNTU_DISK)
	time $(PYTHON) ./tools/cloud/create.py -l ${LAB} -s /opt/imgs -z ./trusty-server-cloudimg-amd64-disk1.img -t 2role > config_file

prepare-2role-cobbler:
	@echo "$(CYAN)>>>> Preparing 2_role boxes for cobbler...$(RESET)"
	test -e trusty-server-cloudimg-amd64-disk1.img || wget -nv $(UBUNTU_DISK)
	time $(PYTHON) ./tools/cloud/create.py -b net -l ${LAB} -s /opt/imgs -z ./trusty-server-cloudimg-amd64-disk1.img -t 2role > config_file

prepare-fullha:
	@echo "$(CYAN)>>>> Preparing full HA boxes...$(RESET)"
	test -e trusty-server-cloudimg-amd64-disk1.img || wget -nv $(UBUNTU_DISK)
	time $(PYTHON) ./tools/cloud/create.py -l ${LAB} -s /opt/imgs -z ./trusty-server-cloudimg-amd64-disk1.img -t fullha > config_file

prepare-fullha-cobbler:
	@echo "$(CYAN)>>>> Preparing full HA boxes for cobbler...$(RESET)"
	test -e trusty-server-cloudimg-amd64-disk1.img || wget -nv $(UBUNTU_DISK)
	time $(PYTHON) ./tools/cloud/create.py -b net -l ${LAB} -s /opt/imgs -z ./trusty-server-cloudimg-amd64-disk1.img -t fullha > config_file


give-a-time:
	sleep 180

install-aio:
	@echo "$(CYAN)>>>> Installing AIO...$(RESET)"
	#time $(PYTHON) ./tools/deployers/install_coi.py -s all-in-one -c config_file -u root
	time timeout --preserve-status -s 15 -k 10060 10000 $(PYTHON) ./tools/deployers/install_aio_coi.py -c config_file -u root

install-2role:
	@echo "$(CYAN)>>>> Installing 2_role multinode...$(RESET)"
	#time $(PYTHON) ./tools/deployers/install_coi.py -s 2role -c config_file -u root
	time timeout --preserve-status -s 15 -k 10060 10000 $(PYTHON) ./tools/deployers/install_aio_2role.py -c config_file -u root
	touch 2role

install-2role-cobbler:
	@echo "$(CYAN)>>>> Installing 2_role multinode with cobbler...$(RESET)"
	#time $(PYTHON) ./tools/deployers/install_aio_2role.py -e -s 2role -c config_file -u root
	time $(PYTHON) ./tools/deployers/install_aio_2role.py -e -c config_file -u root
	touch 2role

install-fullha:
	@echo "$(CYAN)>>>> Installing full HA setup...$(RESET)"
	#time $(PYTHON) ./tools/deployers/install_coi.py -s fullha -c config_file -u root
	time timeout --preserve-status -s 15 -k 10060 10000 time $(PYTHON) ./tools/deployers/install_fullha.py -c config_file -u root

install-fullha-cobbler:
	@echo "$(CYAN)>>>> Installing full HA setup with cobbler...$(RESET)"
	#time $(PYTHON) ./tools/deployers/install_coi.py -s fullha -e -c config_file -u root
	time $(PYTHON) ./tools/deployers/install_fullha.py -e -c config_file -u root

install-devstack:
	@echo "$(CYAN)>>>> Installing Devstack...$(RESET)"
	time $(PYTHON) ./tools/deployers/install_devstack.py -c config_file  -u localadmin -p ubuntu -r ${TEMPEST_REPO} -b ${TEMPEST_BRANCH}
	#time $(PYTHON) ./tools/deployers/install_coi.py -c config_file  -u localadmin -p ubuntu -s devstack

prepare-devstack-tempest:
	echo "$(CYAN)>>>> Running devstack on tempest...$(RESET)"
	time python ${WORKSPACE}/tempest/tools/install_venv.py
	${WORKSPACE}/tempest/.venv/bin/pip install junitxml python-ceilometerclient nose testresources testtools
	. ${WORKSPACE}/tempest/.venv/bin/activate
	mv ./tempest.conf ${WORKSPACE}/tempest/etc/tempest.conf

prepare-tempest:
	@echo "$(CYAN)>>>> Preparing tempest...$(RESET)"
	time $(PYTHON) ./tools/tempest-scripts/tempest_align.py -c config_file -u localadmin -p ubuntu
	time python ${WORKSPACE}/tempest/tools/install_venv.py
	${WORKSPACE}/tempest/.venv/bin/pip install junitxml python-ceilometerclient nose testresources testtools
	. ${WORKSPACE}/tempest/.venv/bin/activate
	time $(TPATH)/python ./tools/tempest-scripts/tempest_configurator.py -o ./openrc
	test -e 2role && sed -i "s/.*[sS]wift.*\=.*[Tt]rue.*/swift=false/g" ./tempest.conf.jenkins || :
	mv ./tempest.conf.jenkins ${WORKSPACE}/tempest/etc/tempest.conf

run-tests:
	@echo "$(CYAN)>>>> Run tempest tests ...$(RESET)"
	time timeout --preserve-status -s 2 -k ${QA_KILLTIME} ${QA_WAITTIME} /bin/bash ./tools/tempest-scripts/run_tempest_tests.sh || :

run-snap-tests:
	@echo "$(CYAN)>>>> Run tempest tests ...$(RESET)"
	time timeout --preserve-status -s 2 -k ${QA_KILLTIME} ${QA_WAITTIME} /bin/bash ./tools/tempest-scripts/run_snap_tests.sh || :

run-snap-tests-remote:
	@echo "$(CYAN)>>>> Run tempest tests ...$(RESET)"
	time timeout --preserve-status -s 2 -k ${QA_KILLTIME} ${QA_WAITTIME} /bin/bash ./tools/tempest-scripts/run_tempest_remote.sh || :

run-tests-parallel:
	@echo "$(CYAN)>>>> Run tempest tests in parallel ...$(RESET)"
	sed -i 's/testr run/testr run --parallel /g' ./tools/tempest-scripts/run_tempest_tests.sh
	time /bin/bash ./tools/tempest-scripts/run_tempest_tests.sh

shutdownall:
	@echo "$(CYAN)>>>> Shutdown everything ...$(RESET)"
	time $(PYTHON) ./tools/cloud/create.py -l ${LAB} -y

shutdown:
	@echo "$(CYAN)>>>> Shutdown boxes ...$(RESET)"
	time /bin/bash ./tools/libvirt-scripts/lab-snapshot-shutdown.sh ${LAB}

workaround-after:
	@echo "$(CYAN)>>>> Running workarounds...$(RESET)"
	time $(PYTHON) ./tools/tempest-scripts/tempest_align.py -c config_file -u localadmin -p ubuntu

snapshot-revert:
	@echo "$(CYAN)>>>> Resurrecting ${LAB} snapshots ...$(RESET)"
	time /bin/bash ./tools/libvirt-scripts/lab-snapshot-restore.sh ${LAB}
	sleep 30

devstack-snap-prepare:
	@echo "$(CYAN)>>>> Preparing devstack for tests run ...$(RESET)"
	time /bin/bash ./tools/libvirt-scripts/devstack_prepare.sh ${LAB}

snapshot-destroy:
	@echo "$(CYAN)>>>> Preparing for snapshotting ...$(RESET)"
	/bin/bash ./tools/libvirt-scripts/lab-snapshot-destroy.sh ${LAB}

snapshot-create:
	@echo "$(CYAN)>>>> Create snapshotted lab ...$(RESET)"
	/bin/bash ./tools/libvirt-scripts/lab-snapshot-create.sh ${LAB}

snap-tempest-prepare:
	@echo "$(CYAN)>>>> Prepare tempest for snapshotted lab ...$(RESET)"
	time /bin/bash ./tools/libvirt-scripts/snaplab_prepare.sh ${LAB}
	time python ${WORKSPACE}/tempest/tools/install_venv.py
	${WORKSPACE}/tempest/.venv/bin/pip install junitxml python-ceilometerclient nose testresources testtools
	. ${WORKSPACE}/tempest/.venv/bin/activate
	time $(TPATH)/python ./tools/tempest-scripts/tempest_configurator.py -o ./openrc
	test -e 2role && sed -i "s/.*[sS]wift.*\=.*[Tt]rue.*/swift=false/g" ./tempest.conf.jenkins || :
	mv ./tempest.conf.jenkins ${WORKSPACE}/tempest/etc/tempest.conf

init: venv requirements

aio: init prepare-aio give-a-time install-aio

2role: init prepare-2role give-a-time install-2role

2role-cobbler: init prepare-2role-cobbler give-a-time install-2role-cobbler

fullha: init prepare-fullha give-a-time install-fullha

fullha-cobbler: init prepare-fullha-cobbler give-a-time install-fullha-cobbler

run-tempest: prepare-tempest run-tests

run-tempest-parallel: prepare-tempest run-tests-parallel

devstack: init prepare-devstack give-a-time install-devstack

devstack-snapshot: init snapshot-revert devstack-snap-prepare

devstack-tempest: prepare-devstack-tempest run-tests

full-aio: aio run-tempest

full-aio-quick: aio run-tempest-parallel

full-2role: 2role run-tempest

full-2role-quick: 2role run-tempest-parallel

full-fullha: fullha run-tempest

snap-aio-create: snapshot-destroy aio workaround-after snapshot-create
snap-2role-create: snapshot-destroy 2role workaround-after snapshot-create
snap-fullha-create: snapshot-destroy fullha workaround-after snapshot-create
snap-devstack-create: snapshot-destroy devstack snapshot-create
snap-devstack-tempest: snapshot-revert devstack-snap-prepare prepare-devstack-tempest
snap-devstack-tempest-remote: init snapshot-revert devstack-snap-prepare
snap-tempest: snapshot-revert snap-tempest-prepare

test-me:
	@echo "$(CYAN)>>>> test your commands :) ...$(RESET)"
	echo ${LAB}
	echo ${WORKSPACE}
	ls ${WORKSPACE}

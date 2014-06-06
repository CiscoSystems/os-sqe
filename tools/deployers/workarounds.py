#!/usr/bin/env python
__author__ = 'sshnaidm'

from fabric.api import sudo, settings, run, hide, put, shell_env, local, cd, get
from fabric.contrib.files import sed, append, exists
import time

def fix_dummy(s):
    print "There was a workaround %s before" % s

def fix_aio(step, func=run, sudo_flag=False):
    if step == "before_script":
        pass
    elif step == "before_run":
        for i in xrange(4):
            func('echo -e "\npuppet apply /etc/puppet/manifests/site.pp\n" >> /root/install_icehouse_cisco.sh')
        sed("/root/install_icehouse_cisco.sh", "patch -p1", "patch -p1 -N", use_sudo=sudo_flag)
    elif step == "after_run":
        pass
    elif step == "":
        return func("echo Opa :)")

def fix_2role(step, func=run, sudo_flag=False):
    if step == "before_script":
        pass
    elif step == "before_run":
        #sed("/root/install_icehouse_cisco.sh", "puppet apply /etc/puppet/manifests/site.pp", "", use_sudo=sudo_flag)
        #sed("/root/install_icehouse_cisco.sh", "patch -p1", "patch -p1 -N", use_sudo=sudo_flag)
        #sed("/root/install_icehouse_cisco.sh", "all_in_one", "2_role", use_sudo=sudo_flag)
        func("ping openstack-repo.cisco.com -c 1")
        func("env | grep interface")
    elif step == "controls_before_setup":
        sed("./setup.sh", "patch -p1", "patch -p1 -N")
    elif step == "controls_after_setup":
        func("puppet agent --enable")
        func("puppet agent -td --server=build-server.domain.name --pluginsync")
    elif step == "build_before_puppet_apply":
        #sed("/usr/share/puppet/modules/neutron/manifests/agents/ovs.pp", ".*neutron::plugins::ovs::port.*", "")
        #func('puppet apply -v /etc/puppet/manifests/site.pp')
        pass
    elif step == "build_after_puppet_apply":
        #sed("/usr/share/puppet/modules/neutron/manifests/agents/ovs.pp", ".*neutron::plugins::ovs::port.*", "")
        #func('puppet apply -v /etc/puppet/manifests/site.pp')
        pass
    elif step == "":
        return func("echo Dude :)")

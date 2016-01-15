from fabric.api import task, settings, cd

@task
def install(lab_cfg, repo, ref):
    from lab.laboratory import Laboratory

    name = 'networking-cisco'

    lab = Laboratory(config_path=lab_cfg)
    for controller in lab.controllers():
        installed_rpm = controller.run('rpm -qa | grep {0} || true'.format(name), )
        installed_pip = controller.run('pip freeze | grep {0} || true'.format(name))
        if installed_rpm:
            print 'Installed rpm package: ', installed_rpm
            print 'Uninstalling...'
            controller.run('sudo rpm -e {0}'.format(installed_rpm))
        if installed_pip:
            print 'Installed dev (using pip) version: ', installed_pip
            controller.run('sudo pip uninstall -y {0}'.format(name))

        # install pip
        controller.run('curl --silent --show-error --retry 5 https://bootstrap.pypa.io/get-pip.py | sudo python')

        # install new version
        controller.run('rm -rf {0}'.format(name))
        controller.run('mkdir {0}'.format(name))
        with cd(name):
            controller.run('git init')
            controller.run('git fetch {0} {1} && git checkout FETCH_HEAD'.format(repo, ref))
            controller.run("sed -i '/^neutron/d' ./requirements.txt")
            controller.run('sudo pip install .')

        # enable debug and verbose
        controller.run("sudo sed -i 's/^verbose = False/verbose = True/' /etc/neutron/neutron.conf")
        controller.run("sudo sed -i 's/^debug = False/debug = True/' /etc/neutron/neutron.conf")

        # restart neutron-server
        controller.run('sudo systemctl restart neutron-server')

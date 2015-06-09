from fabric.api import local, run, get, put, settings, cd
import ConfigParser
import time
import smtplib

INSTALLER_COMMAND = \
    "source vmtpenv/bin/activate && export ANSIBLE_HOST_KEY_CHECKING=False " \
    "&& python ./src/installer.py -c config.cfg -n vlan --cisco_vlan_plugin -p RHEL7" \
    " --osp_version juno --rh_username ymorkovn@cisco.com --rh_password 280778 "


class EmcController:
    def __init__(self, ip):
        self.lab_ip = ip

    @staticmethod
    def read_save_config(tb_name):
        local('wget -N http://172.29.173.233/nightly/' + tb_name)
        config = ConfigParser.RawConfigParser()
        config.optionxform = str
        config.read(tb_name)
        return config

    def emc_install(self, tb_name, args):
        config = EmcController.read_save_config(tb_name)
        controller_ip = config.get("PACKSTACK_CONFIG_VLAN", "CONFIG_CONTROLLER_HOST")
        with settings(host_string='{user}@{ip}'.format(user="localadmin", ip=self.lab_ip),
                      password="ubuntu"):
            put(local_path=tb_name, remote_path="~/installer/config.cfg")
            with cd("~/installer"):
                run(INSTALLER_COMMAND + args + ' < answers_install', warn_only=False)
                time.sleep(100)
                run(INSTALLER_COMMAND + args + ' < answers', warn_only=False)
        with settings(host_string='root@{ip}'.format(ip=controller_ip), user='root',
                      password='cisco123', abort_on_prompts=True):
            run('tar -cvf packstack_log.tar /var/tmp/packstack')
            get(remote_path='packstack_log.tar', local_path='packstack_log.tar')
            if not config.get("SETUP", "TB_GATEWAY") == config.get("NETWORK_CONFIG", "GATEWAY"):
                interface = "br-ex" if not config.has_section("NEW_INT") \
                    else config.get("NEW_INT", "int")
                run("ip a add {gateway}/{prefix} dev {int}".
                    format(gateway=config.get("NETWORK_CONFIG", "GATEWAY"),
                           prefix=config.get("NETWORK_CONFIG", "SUBNET").split("/")[1],
                           int=interface))
                run("ip l s {int} up".format(int=interface))
            self.configure_tempest(controller_ip)

    def emc_update_installer(self, tb_name, url, repo_tag, args):
        print("update")
        config = EmcController.read_save_config(tb_name)
        controller_ip = config.get("PACKSTACK_CONFIG_VLAN", "CONFIG_CONTROLLER_HOST")
        url_tag = url.split("junoplus-")[1].split("/")[0]
        repo_tag = repo_tag.split('.cisco')[0]
        with settings(host_string='{user}@{ip}'.format(user="localadmin", ip=self.lab_ip),
                      password="ubuntu"):
            put(local_path=tb_name, remote_path="~/updater/config.cfg")
            with cd("~/updater"):
                run('ssh-keygen -f "/home/localadmin/.ssh/known_hosts" -R {ip}'.
                    format(ip=controller_ip))
                run(INSTALLER_COMMAND + args + ' --juno_emc_repo_tag {repo_tag}'
                                        ' --juno_emc_url_tag {url_tag} -y'.format(
                        url_tag=url_tag, repo_tag=repo_tag), warn_only=False)

    def emc_test(self, tb_name, test_list=''):
        print "Testing EMC"
        config = EmcController.read_save_config(tb_name)
        controller_ip = config.get("PACKSTACK_CONFIG_VLAN", "CONFIG_CONTROLLER_HOST")
        with settings(host_string='root@{ip}'.format(ip=controller_ip), password='cisco123'):
            self.configure_tempest(controller_ip)
            with cd('/root/tempest/'):
                run('rm tempest/scenario/test_network_vlan_transparency.py')
                run('source .tox/full/bin/activate && ./run_tempest.sh -N -- {filter_or_list}'.format(
                        filter_or_list=test_list))
                run('pip install junitxml')
                run('testr last --subunit | subunit-1to2 | subunit2junitxml --output-to=tempest_results.xml')
                get(remote_path='tempest_results.xml', local_path='tempest_results.xml')

    def configure_tempest(self, controller_ip):
        with cd('/root'):
            run('yum install -y  bash-completion git gcc libffi-devel python-devel openssl-devel python-junitxml')
            run('rm -rf tempest')
            run('git clone https://github.com/redhat-openstack/tempest.git --branch juno')
            with cd('tempest/'):
                run('python tools/config_tempest.py'
                    ' --image "http://download.cirros-cloud.net/0.3.3/cirros-0.3.3-x86_64-disk.img"'
                    ' --create identity.uri http://{ip}:5000/v2.0/'
                    ' identity.username demo identity.password demo identity.auth_version v2'
                    ' identity.tenant_name demo identity.admin_domain_name Default'
                    ' auth.allow_tenant_isolation True auth.tempest_roles _member_'
                    ' network.ipv6 false network.ipv6_subnet_attributes false'
                    ' compute-feature-enabled.live_migration false'
                    ' identity.admin_username admin identity.admin_password admin'.format(
                        ip=controller_ip))
                run('git checkout -b kilo origin/kilo')
                # run('git fetch  https://github.com/cisco-openstack/tempest.git proposed '
                #     '&& git checkout FETCH_HEAD && git checkout -b proposed')
                run('pip install tox testrepository')
                run('testr init')
                run('tox -efull --notest')

    def email_report(self, sendto,  tb_name, url, repo_tag,
                     server_name='outbound.cisco.com'):
        from email.mime import multipart, text
        server = smtplib.SMTP(server_name)
        mail = multipart.MIMEMultipart()
        sender = "EMC Update"
        mail['From'] = sender
        mail['To'] = sendto
        mail['Subject'] = "EMC updated Testbed {testbed}".\
            format(testbed=tb_name)
        mail.attach(
            text.MIMEText(
"""Testbed: {tb_name}
juno_emc_url_tag: {url}
juno_emc_repo_tag: {repo_tag}
""".format(tb_name=tb_name, url=url, repo_tag=repo_tag)))
        try:
            server.sendmail(sender, sendto, mail.as_string())
        except Exception, e:
            raise e
        finally:
            server.quit()

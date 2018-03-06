from lab.nodes.cimc_server import CimcServer, CimcController, CimcCompute, CimcVts, CimcCeph
from lab import decorators


class MercuryController(CimcController):
    short = 'C'


class MercuryCompute(CimcCompute):
    short = 'c'


class MercuryVts(CimcVts):
    """ Host which hosts a number of VTS related libvirt VMs, usually vtcX and vtsrX.
        Normal VTS installation consists from 2 such hosts
    """
    short = 'v'


class MercuryCeph(CimcCeph):
    short = 's'


class MercuryMgm(CimcServer):
    short = 'm'

    @staticmethod
    def create_from_actual(ip, password):
        from lab.with_config import WithConfig
        from lab.server import Server
        import yaml

        separator = 'separator'
        cmds = ['ciscovim install-status', 'cat setup_data.yaml', 'grep -E "image_tag|RELEASE_TAG" defaults.yaml']
        cmd = ' ; echo {} ; '.format(separator).join(cmds)

        mgm = Server(ip=ip, username=WithConfig.SQE_USERNAME, password=None)

        while True:
            try:
                a = mgm.exe(cmd)
                status, setup_data_body, grep = a.split('separator')
                setup_data_dic = yaml.load(setup_data_body)
                release_tag = grep.split('\n')[1].split(':')[-1].strip()
                gerrit_tag = grep.split('\n')[2].split(':')[-1].strip()
                mgm.username = 'root'
                mgm.password = password
                return mgm, status, setup_data_dic, release_tag, gerrit_tag
            except ValueError:  # means username/password combination wrong
                mgm.username = 'root'
                mgm.password = password
                mgm.create_user(username=WithConfig.SQE_USERNAME, public_key=WithConfig.PUBLIC_KEY, private_key=WithConfig.PRIVATE_KEY)
                continue



    def r_collect_info(self, regex):
        body = ''
        for cmd in [self.log_grep_cmd(log_files='/var/log/mercury/*', regex=regex)]:
            ans = self.exe(cmd=cmd, is_warn_only=True)
            body += self.single_cmd_output(cmd=cmd, ans=ans)
        return body

    def r_configure_nat(self):
        self.exe('iptables -t nat -L | grep -q -F "MASQUERADE  all  --  anywhere             anywhere" || iptables -t nat -A POSTROUTING -o br_api -j MASQUERADE')  # this NAT is only used to access to centralized ceph

    @decorators.section('creating access points on mgmt node')
    def r_create_access_points(self, networks):
        for net in networks:
            cmd = 'ip l | grep br_mgmt.{0} && ip l d br_mgmt.{0}'.format(net.get_vts_vlan())
            self.exe(cmd)
            cmd = 'ip l a link br_mgmt name br_mgmt.{0} type vlan id {0} && ip l s dev br_mgmt.{0} up && ip a a {1} dev br_mgmt.{0}'.format(net.get_vts_vlan(), net.get_ip_with_prefix(-5))
            self.exe(cmd)

    @staticmethod
    def r_get_latest_gerrit_tag():
        import requests

        ans = requests.get('https://cloud-infra.cisco.com/api/v1.0/changeset/?number_only=1&branch=master&namespace=mercury-rhel7-osp10')
        return ans.text

    def r_resolve_power_failure(self):
        self.exe('python openstack/hw_validations.py --resolve-failures power', in_dir='installer-' + self.pod.gerrit_tag)

    @decorators.section('Prepare nfvbench debug')
    def r_nfvbench_debug(self):
        repo_abs_path = self.r_clone_repo('https://wwwin-gitlab-sjc.cisco.com/openstack-perf/dev-utils.git', is_as_sqe=False)
        self.exe('bash dev-utils/container-hookup.sh', in_dir=repo_abs_path + '/nfvbench')

    def r_discover_cisco_bm(self):
        self.exe(cmd='PYTHONPATH=. python tools/discover_cisco_bm.py', in_dir='installer-' + self.pod.gerrit_tag)

from lab.nodes.cimc_server import CimcServer, CimcController, CimcCompute, CimcVts, CimcCeph
from lab import decorators


class MercuryController(CimcController):
    pass


class MercuryCompute(CimcCompute):
    pass


class MercuryVts(CimcVts):
    pass


class MercuryCeph(CimcCeph):
    pass


class MercuryMgm(CimcServer):
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

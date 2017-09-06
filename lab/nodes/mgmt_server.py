from lab import decorators
from lab.nodes.cimc_server import CimcServer


class CimcDirector(CimcServer):
    ROLE = 'director-n9'

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

    @decorators.section('Create/activate sqe user')
    def r_create_sqe_user(self):
        from lab.server import Server

        if not self.exe(cmd='grep {} /etc/passwd'.format(self.SQE_USERNAME), is_warn_only=True):
            tmp_password = 'tmp-password'
            encrypted_password = self.exe(cmd='openssl passwd -crypt ' + tmp_password).split()[-1]  # encrypted password may contain Warning
            self.exe(cmd='adduser -p ' + encrypted_password + ' ' + self.SQE_USERNAME)
            self.exe(cmd='echo "{0} ALL=(root) NOPASSWD:ALL" | tee -a /etc/sudoers.d/{0}'.format(self.SQE_USERNAME))
            self.exe(cmd='chmod 0440 /etc/sudoers.d/' + self.SQE_USERNAME)

            server = Server(ip=self.ssh_ip, username=self.SQE_USERNAME, password=tmp_password)
            server.exe('mkdir -p .ssh && chmod 700 .ssh')
            server.exe('echo "{}" > .ssh/id_rsa && chmod 600 .ssh/id_rsa'.format(self.PRIVATE_KEY))
            server.exe('echo "{}" > .ssh/id_rsa.pub && cp .ssh/id_rsa.pub .ssh/authorized_keys && chmod 600 .ssh/authorized_keys'.format(self.PUBLIC_KEY))
            gitlab_public = 'wwwin-gitlab-sjc.cisco.com,10.22.31.77 ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBJZlfIFWs5/EaXGnR9oXp6mCtShpvO2zKGqJxNMvMJmixdkdW4oPjxYEYP+2tXKPorvh3Wweol82V3KOkB6VhLk='
            server.exe('echo {} > .ssh/known_hosts'.format(gitlab_public))

    @decorators.section('Prepare nfvbench debug')
    def r_nfvbench_debug(self):
        repo_abs_path = self.r_clone_repo('https://wwwin-gitlab-sjc.cisco.com/openstack-perf/dev-utils.git', is_as_sqe=False)
        self.exe('bash dev-utils/container-hookup.sh', in_dir=repo_abs_path + '/nfvbench')

    def r_discover_cisco_bm(self):
        self.exe(cmd='PYTHONPATH=. python tools/discover_cisco_bm.py', in_dir='installer-' + self.pod.gerrit_tag)

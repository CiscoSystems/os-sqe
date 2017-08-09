from lab import decorators
from lab.nodes.cimc_server import CimcServer


class CimcDirector(CimcServer):
    ROLE = 'director-n9'

    RELEASE_NAMES = {'2.1': 'master', '2.0': 'newton', '1.0': 'liberty'}

    @decorators.section('Get VIM version')
    def r_get_version(self):
        import json
        import yaml

        ans = self.exe(cmd='sudo grep -E "image_tag|namespace|RELEASE_TAG" /root/openstack-configs/defaults.yaml', is_as_sqe=True)
        release_tag = ans.split('\r\n')[0].split(':')[-1].strip()

        a = {'gerrit_tag': ans.split('\r\n')[1].split(':')[-1].strip(),
             'container_namespace': ans.split('\r\n')[2].split(':')[-1].strip(),
             'mechanism': self.pod.driver,
             'release_tag': release_tag,
             'release_name': self.RELEASE_NAMES[release_tag.rsplit('.', 1)[0]]}
        if a['mechanism'] == 'vts':
            ans = self.exe('sudo cat /root/vts_config.yaml', is_as_sqe=True)
            active_vtc_ips = [x['vtc']['api_ip'] for x in yaml.load(ans)['vts_hosts'].values()]
            for vtc in self.pod.vtc:
                if vtc.api_ip not in active_vtc_ips:
                    self.log_warning('"{}" deleted since is not active according to /root/vts_config.yaml'.format(vtc))
                    del self.pod.nodes[vtc.id]
            if not len(self.pod.vtc):
                raise RuntimeError('Not VTC is activated on this lab')
            a['mech_ver'] = self.pod.vtc[0].r_vtc_get_version()
        else:
            a['mech_ver'] = 'vpp XXXX'
        with self.open_artifact('{}-versions.txt'.format(self.pod), 'w') as f:
            f.write(json.dumps(a, sort_keys=True, indent=4, separators=(',', ': ')))

        return a
    
    def r_collect_logs(self, regex):
        body = ''
        for cmd in [self._form_log_grep_cmd(log_files='/var/log/mercury/installer/*', regex=regex)]:
            ans = self.exe(cmd=cmd, is_warn_only=True)
            body += self._format_single_cmd_output(cmd=cmd, ans=ans)
        return body

    def r_configure_mx_and_nat(self):
        mx_ip, mx_gw_ip = self.get_ip_mx_with_prefix(), self.get_gw_mx_with_prefix()
        self.exe('ip a flush dev br_mgmt')
        self.exe('ip a a {} dev br_mgmt'.format(mx_ip))
        self.exe('ip a a {} dev br_mgmt'.format(mx_gw_ip))
        self.exe('iptables -t nat -L | grep -q -F "MASQUERADE  all  --  anywhere             anywhere" || iptables -t nat -A POSTROUTING -o br_api -j MASQUERADE')  # this NAT is only used to access to centralized ceph

    @decorators.section('creating access points on mgmt node')
    def r_create_access_points(self, networks):
        for net in networks:
            cmd = 'ip l | grep br_mgmt.{0} && ip l d br_mgmt.{0}'.format(net.get_vts_vlan())
            self.exe(cmd)
            cmd = 'ip l a link br_mgmt name br_mgmt.{0} type vlan id {0} && ip l s dev br_mgmt.{0} up && ip a a {1} dev br_mgmt.{0}'.format(net.get_vts_vlan(), net.get_ip_with_prefix(-5))
            self.exe(cmd)

    def r_check_intel_nics(self):
        ans = self.exe(cmd='lspci | grep Intel | grep SFP+', is_warn_only=True, is_as_sqe=True)
        if not ans:
            raise RuntimeError('{}: there is no Intel NIC'.format(self))
        # pci_addrs = [x.split()[0] for x in ans.split('\r\n')]
        # for pci_addr in pci_addrs:
        #     bus = int(pci_addr[:2], 16)
        #     card = int(pci_addr[3:5])
        #     port = int(pci_addr[6:])
        #     ans = self.exe('ethtool -i enp{}s{}f{}'.format(bus, card, port), is_warn_only=True)
        #     if 'No such device' in ans:
        #         raise RuntimeError('{}: Intel lspci | grep {} is not seen as iface'.format(self, pci_addr))

    @staticmethod
    def r_get_latest_gerrit_tag():
        import requests

        ans = requests.get('https://cloud-infra.cisco.com/api/v1.0/changeset/?number_only=1&branch=master&namespace=mercury-rhel7-osp10')
        return ans.text

    def r_resolve_power_failure(self):
        ver = self.r_get_version()
        self.exe('python openstack/hw_validations.py --resolve-failures power', in_dir='installer-' + ver['gerrit_tag'])

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

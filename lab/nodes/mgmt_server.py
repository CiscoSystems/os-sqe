from lab import decorators
from lab.nodes.cimc_server import CimcServer


class CimcDirector(CimcServer):
    ROLE = 'director-n9'

    @decorators.section('Getting VIM version tag')
    def r_get_version(self):
        ans = self.exe('grep image_tag openstack-configs/defaults.yaml && grep MECHANISM_DRIVERS openstack-configs/setup_data.yaml && grep namespace openstack-configs/defaults.yaml')
        a = {'gerrit_tag': ans.split('\r\n')[0].split(':')[-1].strip(), 'mechanism': ans.split('\r\n')[1].split(':')[-1].strip(), 'container_namespace': ans.split('\r\n')[2].split(':')[-1].strip()}
        if a['mechanism'] == 'vts':
            a['mech_ver'] = self.pod.vtc[0].r_vtc_get_version()
        else:
            a['mech_ver'] = 'vpp XXXX'
        return a
    
    def r_collect_logs(self, regex):
        body = ''
        for cmd in [self._form_log_grep_cmd(log_files='/var/log/mercury/installer/*', regex=regex)]:
            ans = self.exe(command=cmd, is_warn_only=True)
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
        ans = self.exe('lspci | grep Intel | grep SFP+', is_warn_only=True)
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
        self.exe('python openstack/hw_validations.py --resolve-failures power', in_directory='installer-' + ver['gerrit_tag'])

    def r_create_sqe_user(self):
        sqe_username = 'sqe'
        if not self.exe(command='grep {} /etc/passwd'.format(sqe_username), is_warn_only=True):
            tmp_password = 'cisco123tmp'
            encrypted_password = self.exe(command='openssl passwd -crypt ' + tmp_password).split()[-1]  # encrypted password may contain Warning
            self.exe(command='adduser -p ' + encrypted_password + ' ' + sqe_username)
            self.exe(command='echo "{0} ALL=(root) NOPASSWD:ALL" | tee -a /etc/sudoers.d/{0}'.format(sqe_username))
            self.exe(command='chmod 0440 /etc/sudoers.d/' + sqe_username)

            self._server.username, self._server.password = sqe_username, tmp_password  # start using sqe user with tmp password
            with open(self.KEY_PRIVATE_PATH) as f:
                self._server.put_string_as_file_in_dir(string_to_put=f.read(), file_name='id_rsa', in_directory='.ssh')
            with open(self.KEY_PUBLIC_PATH) as f:
                self._server.put_string_as_file_in_dir(string_to_put=f.read(), file_name='id_rsa.pub', in_directory='.ssh')
            self.exe(command='cp .ssh/id_rsa.pub .ssh/authorized_keys && chmod 700 .ssh && chmod 600 .ssh/*')

        self._server.username, self._server.password = sqe_username, None  # start using sqe user with ssh key
        self.exe(command='git config --global user.name "Performance team" && git config --global user.email "perf-team@cisco.com" && git config --global push.default simple')

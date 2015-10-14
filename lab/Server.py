class Server(object):
    def __init__(self, ip, username, password, hostname='Unknown', ssh_public_key='N/A', ssh_port=22):
        self.ip = ip
        self.ip_mac = 'UnknownInServer'
        self.hostname = hostname
        self.username = username
        self.password = password
        self.ssh_public_key = ssh_public_key
        self.ssh_port = ssh_port

        self.ipmi = {'ip': 'UnknownInServer', 'username': 'UnknownInServer', 'password': 'UnknownInServer'}
        self.ucsm = {'ip': 'UnknownInServer', 'username': 'UnknownInServer', 'password': 'UnknownInServer', 'service-profile': 'UnknownInServer',
                     'iface_mac': {'UnknownInServer': 'UnknownInServer'}}

    def __repr__(self):
        return 'sshpass -p {0} ssh {1}@{2}'.format(self.password, self.username, self.ip)

    def set_ipmi(self, ip, username, password):
        self.ipmi['ip'] = ip
        self.ipmi['username'] = username
        self.ipmi['password'] = password

    def set_ucsm(self, ip, username, password, service_profile, iface_mac):
        self.ucsm['ip'] = ip
        self.ucsm['username'] = username
        self.ucsm['password'] = password
        self.ucsm['service-profile'] = service_profile
        self.ucsm['iface_mac'] = iface_mac

    def get_mac(self, iface_name):
        return self.ucsm['iface_mac'].get(iface_name, 'UnknownInServer')

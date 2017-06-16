class N9PortChannel(object):
    def __init__(self, n9, dic):
        self.n9 = n9
        self._dic = dic
        self._ports = []  # belonging to this port-channel

    @property
    def ports(self):
        return self._ports

    @property
    def pc_id(self):
        return self._dic['port-channel']

    @property
    def name(self):
        return self._dic.get('name', 'NoName')

    @property
    def mode(self):
        return self._dic['portmode']

    def add_port(self, port):
        self._ports.append(port)

    @staticmethod
    def process_n9_answer(n9, answer):  # process results of sh port-channel status
        pcs = [answer] if type(answer) is dict else answer  # if there is only one port-channel the API returns dict but not a list. Convert to list
        return {x['port-channel']: N9PortChannel(n9=n9, dic=x) for x in pcs}

    def update(self, dic):  # add info from sh int st and sh int br
        self._dic.update(dic)

    # def n9_configure_vpc(self):
    #     vpc = self._requested_topology['vpc']
    #     for pc_id, info in vpc.items():
    #         self.n9_create_port_channel(pc_id=pc_id, desc=info['description'], port_ids=info['ports'], mode=info['mode'], vlans_string=info['vlans'])
    #         if self.get_peer_link_wires():
    #             self.n9_create_vpc(pc_id)

    def handle_port_channel(self, pc_id):
        cmd = ['conf t', 'int port-channel ' + pc_id]
        if self.n9.vpc_domain:
            cmd.append('vpc ' + pc_id)
        self.n9.cmd(cmd=cmd, timeout=60)

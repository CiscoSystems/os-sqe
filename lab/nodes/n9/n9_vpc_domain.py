class N9VpcDomain(object):
    NOT_CONFIGURED = 'not_configured'

    def __init__(self, n9, dic):
        self.n9 = n9
        self._dic = dic

    @property
    def vpc_domain_id(self):
        return self._dic['vpc-domain-id']

    @property
    def is_configured(self):
        return self.vpc_domain_id != self.NOT_CONFIGURED

    @staticmethod
    def process_n9_answer(n9, answer):
        peer_tbl = answer.get('TABLE_peerlink', {'ROW_peerlink': []})['ROW_peerlink']
        vpc_tbl = answer.get('TABLE_vpc', {'ROW_vpc': []})['ROW_vpc']
        vpc_lst = [vpc_tbl] if type(vpc_tbl) is dict else vpc_tbl  # if there is only one vpc the API returns dict but not a list. Convert to list
        vpc_dic = {x['vpc-ifindex']: x for x in vpc_lst}
        assert len(vpc_dic) == int(answer['num-of-vpcs'])  # this is a number of vpc excluding peer-link vpc
        if peer_tbl:
            vpc_dic[peer_tbl['peerlink-ifindex']] = peer_tbl
        return N9VpcDomain(n9=n9, dic=answer), vpc_dic

    def handle_vpc_domain(self, peer_ip, domain_id=1):
        self.n9.n9_cmd(['conf t', 'feature vpc'])
        self.n9.n9_cmd(['conf t', 'vpc domain {0}'.format(domain_id), 'peer-keepalive destination {0}'.format(peer_ip)], timeout=60)

    # def n9_configure_peer_link(self):
    #     peer_link = self._requested_topology['peer-link']
    #     ip = peer_link['ip']
    #     if ip:
    #         pc_id = peer_link['pc-id']
    #         desc = peer_link['description']
    #         port_ids = peer_link['ports']
    #         vlans_string = peer_link['vlans']
    #         self.n9_configure_vpc_domain(peer_ip=ip)
    #         self.n9_create_port_channel(pc_id=pc_id, desc=desc, port_ids=port_ids, vlans_string=vlans_string, mode='trunk', is_peer_link_pc=True)

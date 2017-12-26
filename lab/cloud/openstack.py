from lab.with_log import WithLogMixIn


class OS(WithLogMixIn):
    def __repr__(self):
        return u'cloud {}'.format(self.name)

    def __init__(self, name, mediator, openrc_path):
        self.name = name
        self.mediator = mediator    # Instance of Server to be used to execute CLI commands for this cloud
        self.openrc_path = openrc_path
        self.controls, self.computes, self.images, self.servers = [], [], [], []

    @staticmethod
    def _add_name_prefix(name):
        from lab.cloud import UNIQUE_PATTERN_IN_NAME
        return '{}-{}'.format(UNIQUE_PATTERN_IN_NAME, name)

    def os_cmd(self, cmds, comment='', server=None, is_warn_only=False):
        server = server or self.mediator
        cmd = 'source ' + self.openrc_path + ' && ' + ' && '.join(cmds) + ('# ' + comment if comment else '')
        ans = server.exe(cmd=cmd, is_warn_only=is_warn_only)
        if ans.failed:
            return ans
        return self._process_output(answer=ans)

    @staticmethod
    def _process_output(answer):
        import json

        if not answer:
            return {}
        answer = '[' + answer.replace('}{', '},{') + ']'
        return json.loads(answer)


    def get_fip_network(self):
        ans = self.os_cmd('neutron net-list --router:external=True -c name')
        net_names = ans
        if not net_names:
            return '', 'physnet1'
        fip_network = net_names[0]
        ans = self.os_cmd('neutron net-list -c provider:physical_network --name {0}'.format(fip_network))
        physnet = filter(lambda x: x not in ['provider:physical_network', '|', '+---------------------------+'], ans.split())[0]
        return fip_network, physnet

    @staticmethod
    def _parse_cli_output(output_lines):
        """Borrowed from tempest-lib. Parse single table from cli output.
        :param output_lines:
        :returns: dict with list of column names in 'headers' key and rows in 'values' key.
        """

        if not isinstance(output_lines, list):
            output_lines = output_lines.split('\n')

        if not output_lines[-1]:
            output_lines = output_lines[:-1]  # skip last line if empty (just newline at the end)

        columns = OS._table_columns(output_lines[2])
        is_2_values = len(columns) == 2

        def line_to_row(input_line):
            return [input_line[col[0]:col[1]].strip() for col in columns]

        headers = None
        d2 = {}
        output_list = []
        for line in output_lines[3:-1]:
            row = line_to_row(line)
            if is_2_values:
                d2[row[0]] = row[1]
            else:
                headers = headers or line_to_row(output_lines[1])
                output_list.append({headers[i]: row[i] for i in range(len(columns))})

        return output_list if output_list else [d2]

    @staticmethod
    def _table_columns(first_table_row):
        """Borrowed from tempest-lib. Find column ranges in output line.
        :returns: list of tuples (start,end) for each column detected by plus (+) characters in delimiter line.
        """
        positions = []
        start = 1  # there is '+' at 0
        while start < len(first_table_row):
            end = first_table_row.find('+', start)
            if end == -1:
                break
            positions.append((start, end))
            start = end + 1
        return positions

    def os_create_fips(self, fip_net, how_many):
        cmds = ['neutron floatingip-create ' + fip_net.get_net_name() for _ in  range(how_many)]
        return self.os_cmd(cmds=cmds)

    def os_cleanup(self, is_all=False):
        from lab.cloud.cloud_server import CloudServer
        from lab.cloud.cloud_image import CloudImage
        from lab.cloud.cloud_router import CloudRouter
        from lab.cloud.cloud_network import CloudNetwork
        from lab.cloud.cloud_flavor import CloudFlavor
        from lab.cloud.cloud_project import CloudProject
        from lab.cloud.cloud_security_group import CloudSecurityGroup
        from lab.cloud.cloud_user import CloudUser
        from lab.cloud.cloud_key_pair import CloudKeyPair
        from lab.cloud.cloud_port import CloudPort
        from lab.cloud.cloud_server_group import CloudServerGroup

        CloudServer.srv_cleanup(cloud=self, is_all=is_all)

        CloudPort.cleanup(cloud=self, is_all=is_all)
        CloudRouter.cleanup(cloud=self, is_all=is_all)
        CloudPort.cleanup(cloud=self, is_all=is_all)
        CloudNetwork.cleanup(cloud=self, is_all=is_all)
        CloudKeyPair.cleanup(cloud=self, is_all=is_all)
        CloudImage.img_cleanup(cloud=self, is_all=is_all)
        CloudFlavor.cleanup(cloud=self, is_all=is_all)
        CloudProject.cleanup(cloud=self, is_all=is_all)
        CloudSecurityGroup.cleanup(cloud=self, is_all=is_all)
        CloudServerGroup.cleanup(cloud=self, is_all=is_all)
        CloudUser.cleanup(cloud=self, is_all=is_all)

    def os_quota_set(self):
        from lab.cloud.cloud_project import CloudProject

        admin_id = [x.id for x in CloudProject.list(cloud=self) if x.name == 'admin'][0]
        self.os_cmd(cmds=['openstack quota set --instances 1000 --cores 2000 --ram 512000 --networks 100 --subnets 300 --ports 500 {}'.format(admin_id)])

    def os_all(self):
        from lab.cloud.cloud_host import CloudHost
        from lab.cloud.cloud_server import CloudServer
        from lab.cloud.cloud_image import CloudImage

        self.controls, self.computes = CloudHost.host_list(cloud=self)

        a = self.os_cmd(cmds=['openstack image list | grep  -vE "\+|ID" |cut -c 3-38 | while read id; do openstack image show $id -f json; done',
                              'openstack server list | grep  -vE "\+|ID" |cut -c 3-38 | while read id; do openstack server show $id -f json; done'])
        for dic in a:
            if 'disk_format' in dic:
                self.images.append(CloudImage(cloud=self, dic=dic))
            elif 'hostId' in dic:
                self.servers.append(CloudServer(cloud=self, dic=dic))
        return self
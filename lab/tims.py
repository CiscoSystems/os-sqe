from lab.with_log import WithLogMixIn
from lab.with_config import WithConfig


class Tims(WithLogMixIn, WithConfig):
    FOLDERS = {'HIGH AVAILABILITY': 'Tcbr1841f', 'NEGATIVE': 'Tcbr1979f', 'VTS PERF AND SCALE': 'Tcbr1840f', 'PERFOMANCE_AND_SCALE': 'Tcbr1840f', 'API_TEST': 'Tcbr2001f'}
    NAMESPACE_TO_BRANCH = {'mercury-rhel7-osp10': 'master', 'mercury-rhel7-osp10-plus': 'newton', 'mercury-rhel7-osp8': 'liberty'}
    MECHANISM_TO_TOPOLOGY = {'vts': 'VTS/VLAN', 'vpp': 'VPP/VLAN'}
    POD_TO_CONF_ID = {'g7-2-vts': 'Tcbr8154g',
                      'g7-2-vpp': 'Tcbr96912g',
                      'marahaika-vts': 'Tcbr9367g',
                      'marahaika-vpp': 'Tcbr114510g',
                      'c35bottom-vts': 'Tcbr115582g',
                      'c35bottom-vpp': 'Tcbr115583g',
                      'i11tb3-vpp':    'Tcbr114510g'}
    TOKENS = {'kshileev': '0000003933000000000D450000000000',
              'nfedotov': '26520000006G00005F42000077044G47',
              'dratushn': '000000525F7G007900000000006G4700',
              'ymorkovn': '6B02004H0000005600003B0000000000'}

    TIMS_PROJECT_ID = 'Tcbr1p'

    _OPERATION_ENTITY = 'entity'
    _OPERATION_UPDATE = 'update'
    _OPERATION_SEARCH = 'search'

    def __init__(self, pod):
        import getpass
        import os

        self.pod = pod
        self._conf_id = Tims.POD_TO_CONF_ID[str(self.pod)]
        self._versions = pod.mgmt.r_get_version()
        self._mercury_version = self._versions['gerrit_tag']
        self._branch = Tims.NAMESPACE_TO_BRANCH[self._versions['container_namespace']]
        self._topo = Tims.MECHANISM_TO_TOPOLOGY[self._versions['mechanism']]
        self._dima_common_part_of_logical_id = ':{}-{}:{}'.format(self._branch, self._mercury_version, self._topo)

        self._jenkins_text = os.getenv('BUILD_URL', None) or 'run off jenkins'
        user_token = os.getenv('TIMS_USER_TOKEN', None)  # some Jenkins jobs define this variable in form user-token
        if user_token and user_token.count('-') == 1:
            username, token = user_token.split('-')
        else:
            user1 = os.getenv('BUILD_USER_ID', 'user_not_defined')  # some Jenkins jobs define this variable
            user2 = os.getenv('BUILD_USER_EMAIL', 'user_not_defined').split('@')[0]  # finally all Jenkins jobs define this variable
            user3 = getpass.getuser()
            username, token = None, None
            for user in [user1, user2, user3]:
                if user in self.TOKENS.keys():
                    username, token = user, self.TOKENS[user]
                    break

        self._xml_tims_wrapper = '''<Tims xmlns="http://tims.cisco.com/namespace" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xlink="http://www.w3.org/1999/xlink"
                                    xsi:schemaLocation="http://tims.cisco.com/namespace http://tims.cisco.com/xsd/Tims.xsd">
                                    <Credential user="{}" token="{}"/>
                                        {{body}}
                                    </Tims>
                                 '''.format(username, token) if username else None

    def __repr__(self):
        return u'TIMS'

    def _api_post(self, operation, body):
        import requests

        if not self._xml_tims_wrapper:
            self.log('No way to detect the user who is running the test, nothing will be published in TIMS', level='error')
            return False
        else:
            data = self._xml_tims_wrapper.format(body=body)
            response = requests.post("http://tims.cisco.com/xml/{}/{}.svc".format(self.TIMS_PROJECT_ID, operation), data=data)
            if u"Error" in response.content.decode():
                raise RuntimeError(response.content)
            return response.content

    def search_test_case(self, test_cfg_path):
        body = '''<Search scope="project" root="{}" entity="case" casesensitive="true">
                    <TextCriterion operator="is">
                        <FieldName><![CDATA[Logical ID]]></FieldName>
                        <Value><![CDATA[{}]]></Value>
                        </TextCriterion>
                  </Search>'''.format(self.TIMS_PROJECT_ID, test_cfg_path)

        res = self._api_post(operation=self._OPERATION_SEARCH, body=body)
        return res.split('</SearchHit>')[0].rsplit('>', 1)[-1] if 'SearchHit' in res else ''

    def search_result(self, logical_id):
        body = '''<Search scope="project" root="{proj_id}" entity="result" casesensitive="true">
                    <TextCriterion operator="is">
                        <FieldName><![CDATA[Logical ID]]></FieldName>
                        <Value><![CDATA[{logical_id}]]></Value>
                        </TextCriterion>
                  </Search>'''.format(proj_id=self.TIMS_PROJECT_ID, logical_id=logical_id)

        res = self._api_post(operation=self._OPERATION_SEARCH, body=body)
        return res.split('</SearchHit>')[0].rsplit('>', 1)[-1] if 'SearchHit' in res else ''

    def update_create_test_case(self, test_cfg_path):
        import json

        case_id = self.search_test_case(test_cfg_path=test_cfg_path)
        logical_or_case_id = '<ID xlink:href="http://tims.cisco.com/xml/{0}/entity.svc">{0}</ID>\n<LogicalID>{1}</LogicalID>'.format(case_id, test_cfg_path) if case_id else '<LogicalID>{}</LogicalID>'.format(test_cfg_path)
        cfg_body = self.read_config_from_file(config_path=test_cfg_path, directory='ha')
        folder_name = cfg_body[0].get('Folder', '')
        if not folder_name or folder_name not in self.FOLDERS:
            self.log('test {} is not updated since does not specify correct folder (one of {})'.format(test_cfg_path, self.FOLDERS.keys()))
            return
        try:
            test_title = [x for x in cfg_body if 'Title' in x][0]['Title']
        except IndexError:
            raise ValueError('test {}: does not define - Title: some text'.format(test_cfg_path))
        desc = 'This is the configuration actually used in testing:\n' + json.dumps(cfg_body, indent=5) + \
               '\nuploaded from https://raw.githubusercontent.com/CiscoSystems/os-sqe/master/configs/ha/{}'.format(test_cfg_path)

        body = '''
        <Case>
            <Title><![CDATA[{test_title}]]></Title>
            <Description><![CDATA[{desc}]]></Description>
            {id}
            <WriteAccess>member</WriteAccess>
            <ProjectID xlink:href="http://tims.cisco.com/xml/{project_id}/project.svc">{project_id}</ProjectID>
            <DatabaseID xlink:href="http://tims.cisco.com/xml/NFVICLOUDINFRA/database.svc">NFVICLOUDINFRA</DatabaseID>
            <FolderID xlink:href="http://tims.cisco.com/xml/{folder_id}/entity.svc">{folder_id}</FolderID>
        </Case>
        '''.format(test_title=test_title, desc=desc, id=logical_or_case_id, project_id=self.TIMS_PROJECT_ID, folder_id=self.FOLDERS[folder_name])

        self._api_post(operation=self._OPERATION_UPDATE, body=body)
        return case_id

    def update_pending_result(self, test_cfg_path, test_case_id, desc, status):
        pending_logical_id = test_cfg_path + self._dima_common_part_of_logical_id
        pending_result_id = self.search_result(logical_id=pending_logical_id)

        if not pending_result_id:
            return self.create_new_result(test_cfg_path=test_cfg_path, test_case_id=test_case_id, logical_id=pending_logical_id, desc=desc, status=status)

        body = '''
            <Result>
                <Title><![CDATA[Result {test_cfg_path}]]></Title>
                <Description><![CDATA[{desc}]]></Description>
                <ID xlink:href="http://tims.cisco.com/xml/{result_id}/entity.svc">{result_id}</ID>
                <LogicalID><![CDATA[{logical_id}]]></LogicalID>
                <WriteAccess>member</WriteAccess>
                <ListFieldValue multi-value="true">
                    <FieldName><![CDATA[ Software Version ]]></FieldName>
                    <Value><![CDATA[ {mercury_version} ]]></Value>
                </ListFieldValue>
                <Status>{status}</Status>
                <ConfigID xlink:href="http://tims.cisco.com/xml/{conf_id}/entity.svc">{conf_id}</ConfigID>
                <CaseID xlink:href="http://tims.cisco.com/xml/{test_case_id}/entity.svc">{test_case_id}</CaseID>
            </Result>
        '''.format(test_cfg_path=test_cfg_path, desc=desc, status=status, mercury_version=self._mercury_version, test_case_id=test_case_id, logical_id=pending_logical_id, result_id=pending_result_id, conf_id=self._conf_id)

        ans = self._api_post(operation=self._OPERATION_UPDATE, body=body)
        return ' and pending http://tims/warp.cmd?ent={} updated'.format(ans.split('</ID>')[0].rsplit('>', 1)[-1])

    def create_new_result(self, test_cfg_path, test_case_id, logical_id, desc, status):
        body = '''
        <Result>
                <Title><![CDATA[for {test_cfg_path}]]></Title>
                <Description><![CDATA[{description}]]></Description>
                <LogicalID><![CDATA[{logical_id}]]></LogicalID>
                <Owner>
                        <UserID>kshileev</UserID>
                </Owner>
                <ListFieldValue multi-value="true">
                    <FieldName><![CDATA[ Software Version ]]></FieldName>
                    <Value><![CDATA[ {mercury_version} ]]></Value>
                </ListFieldValue>
                <Status>{status}</Status>
                <CaseID xlink:href="http://tims.cisco.com/xml/{test_case_id}/entity.svc">{test_case_id}</CaseID>
                <ConfigID xlink:href="http://tims.cisco.com/xml/{conf_id}/entity.svc">{conf_id}</ConfigID>

        </Result>
        '''.format(test_cfg_path=test_cfg_path, test_case_id=test_case_id, logical_id=logical_id, description=desc, mercury_version=self._mercury_version, status=status, conf_id=self._conf_id)

        ans = self._api_post(operation=self._OPERATION_ENTITY, body=body)

        return 'and new http://tims/warp.cmd?ent={} created'.format(ans.split('</ID>')[0].rsplit('>', 1)[-1]) if ans else 'No way to report to TIMS since user is not known'

    def publish_result(self, test_cfg_path, results):

        test_case_id = self.update_create_test_case(test_cfg_path=test_cfg_path)
        desc = self._jenkins_text + '\n'
        status = 'passed'
        for res in results:  # [{'worker name': 'VtsScenario',  'exceptions': [], 'params': '...'}, ...]
            desc += res['worker name'] + ' ' + res['params'] + '\n'
            if res['exceptions']:
                status = 'failed'
                desc += '\n'.join(res['exceptions']) + '\n'

        if self.is_artifact_exists('main-results-for-tims.txt'):
            with self.open_artifact('main-results-for-tims.txt', 'r') as f:
                desc += 'MAIN RESULTS:\n' + f.read()

        log_msg = '{} {}: {} {} {} '.format(self.pod, self._mercury_version, test_cfg_path, status.upper(), self._jenkins_text)

        result_url = self.update_pending_result(test_cfg_path=test_cfg_path, test_case_id=test_case_id, desc=desc, status=status)

        with self.open_artifact('tims.html', 'w') as f:
            f.write('<a href="{}">TIMS result</a>'.format(result_url))
        log_msg += result_url
        self.log_to_slack(log_msg)
        self.log(log_msg)

    @staticmethod
    def simulate():
        from lab.laboratory import Laboratory

        tims_lst = [Tims(Laboratory('g7-2-vts.yaml')), Tims(Laboratory('c35bot-vpp.yaml')), Tims(Laboratory('marahaika-vts.yaml'))]
        # available_tc = tims.ls_configs(directory='ha')

        cfgs = ['perf-csr-0-PVP-1-1k.yaml']
        for test_cfg_path in cfgs:
            results = [{'worker name': 'FakeScenario', 'params': 'FAKE params', 'exceptions': []},
                       {'worker name': 'FakeMonitor', 'params': 'FAKE params', 'exceptions': []},
                       ]
            for tims in tims_lst:
                with tims.open_artifact('main-results-for-tims.txt', 'w') as f:
                    f.write('STATUS=passed\nFAKE main results 1\nFAKE main results 2')
                tims.publish_result(test_cfg_path=test_cfg_path, results=results)

if __name__ == '__main__':
    Tims.simulate()

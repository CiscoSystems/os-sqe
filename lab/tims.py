from lab.with_log import WithLogMixIn
from lab.with_config import WithConfig


class Tims(WithLogMixIn, WithConfig):
    MECHANISM_TO_TOPOLOGY = {'vts': 'VTS/VLAN', 'vpp': 'VPP/VLAN'}
    _OPERATION_ENTITY = 'entity'
    _OPERATION_UPDATE = 'update'
    _OPERATION_SEARCH = 'search'

    def __init__(self, pod):
        import getpass
        import json       
        import os
        import requests

        cfg_dic = json.loads(requests.get(url=self.CONFIGS_REPO_URL + '/tims.json').text)

        self.tims_url = cfg_dic['tims']['url']
        self.tims_project_id = cfg_dic['tims']['project_id']
        self.tims_db_name = cfg_dic['tims']['db_name']
        self.tims_folders = cfg_dic['tims']['folders']
        self.tims_project_id = cfg_dic['tims']['project_id']

        self.conf_id = cfg_dic['tims']['configurations'][str(pod)]
        self.branch = pod.git_repo_branch
        self.topo = self.MECHANISM_TO_TOPOLOGY[pod.driver]
        self.gerrit_tag = pod.gerrit_tag
        self.dima_common_part_of_logical_id = ':{}-{}:{}'.format(self.branch, self.gerrit_tag, self.topo)

        self.common_text = str(pod) + ' ' + str(pod.gerrit_tag) + ' ' + os.getenv('BUILD_URL', 'run manually out off jenkins')
        user_token = os.getenv('TIMS_USER_TOKEN', None)  # some Jenkins jobs define this variable in form user-token
        if user_token and user_token.count('-') == 1:
            username, token = user_token.split('-')
        else:
            user1 = os.getenv('BUILD_USER_ID', 'user_not_defined')  # some Jenkins jobs define this variable
            user2 = os.getenv('BUILD_USER_EMAIL', 'user_not_defined').split('@')[0]  # finally all Jenkins jobs define this variable
            user3 = getpass.getuser()  # take username which runs this job
            user_token_dic = cfg_dic['tims']['user_tokens']
            username, token = user_token_dic.items()[0]
            for user in [user1, user2, user3]:
                if user in user_token_dic:
                    username, token = user, user_token_dic[user]
                    break

        self.log('Using {} to report'.format(username))
        self._xml_tims_wrapper = '''<Tims xmlns="http://{url}/namespace" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xlink="http://www.w3.org/1999/xlink"
                                    xsi:schemaLocation="http://{url}/namespace http://{url}/xsd/Tims.xsd">
                                    <Credential user="{user}" token="{token}"/>
                                        {{body}}
                                    </Tims>
                                 '''.format(url=self.tims_url, user=username, token=token) if username else None

    def __repr__(self):
        return u'TIMS'

    def _api_post(self, operation, body):
        import requests

        if not self._xml_tims_wrapper:
            self.log_error('No way to detect the user who is running the test, nothing will be published in TIMS')
            return False
        else:
            data = self._xml_tims_wrapper.format(body=body)
            response = requests.post("http://{}/xml/{}/{}.svc".format(self.tims_url, self.tims_project_id, operation), data=data)
            if u"Error" in response.content.decode():
                raise RuntimeError(response.content)
            return response.content

    def _search_test_case(self, logical_id):
        body = '''<Search scope="project" root="{}" entity="case" casesensitive="true">
                    <TextCriterion operator="is">
                        <FieldName><![CDATA[Logical ID]]></FieldName>
                        <Value><![CDATA[{}]]></Value>
                        </TextCriterion>
                  </Search>'''.format(self.tims_project_id, logical_id)

        res = self._api_post(operation=self._OPERATION_SEARCH, body=body)
        return res.split('</SearchHit>')[0].rsplit('>', 1)[-1] if 'SearchHit' in res else ''

    def _search_result(self, logical_id):
        body = '''<Search scope="project" root="{proj_id}" entity="result" casesensitive="true">
                    <TextCriterion operator="is">
                        <FieldName><![CDATA[Logical ID]]></FieldName>
                        <Value><![CDATA[{logical_id}]]></Value>
                        </TextCriterion>
                  </Search>'''.format(proj_id=self.tims_project_id, logical_id=logical_id)

        res = self._api_post(operation=self._OPERATION_SEARCH, body=body)
        return res.split('</SearchHit>')[0].rsplit('>', 1)[-1] if 'SearchHit' in res else ''

    def _create_update_test_case(self, test_case):
        logical_id = test_case.unique_id
        case_id = self._search_test_case(logical_id=logical_id)
        logical_or_case_id = '<ID xlink:href="http://{url}/xml/{c_id}/entity.svc">{c_id}</ID>\n<LogicalID>{l_id}</LogicalID>'.format(url=self.tims_url, c_id=case_id, l_id=logical_id) if case_id \
            else '<LogicalID>{}</LogicalID>'.format(logical_id)
        desc = 'actual config:\n' + test_case.body_text + '\nurl: https://raw.githubusercontent.com/CiscoSystems/os-sqe/master/configs/ha/{}\n'.format(test_case.path)

        body = '''
        <Case>
            <Title><![CDATA[{test_title}]]></Title>
            <Description><![CDATA[{desc}]]></Description>
            {id}
            <WriteAccess>member</WriteAccess>
            <ProjectID xlink:href="http://{url}/xml/{project_id}/project.svc">{project_id}</ProjectID>
            <DatabaseID xlink:href="http://{url}/xml/{db_name}/database.svc">{db_name}</DatabaseID>
            <FolderID xlink:href="http://{url}/xml/{folder_id}/entity.svc">{folder_id}</FolderID>
        </Case>
        '''.format(test_title=test_case.title, url=self.tims_url, desc=desc, id=logical_or_case_id, project_id=self.tims_project_id, folder_id=self.tims_folders[test_case.folder], db_name=self.tims_db_name)

        self._api_post(operation=self._OPERATION_UPDATE, body=body)
        if not case_id:
            case_id = self._search_test_case(logical_id=logical_id)
            return case_id, 'created'
        else:
            return case_id, 'updated'

    def _create_update_result(self, test_cfg_path, test_case_id, status, text):
        pending_logical_id = test_cfg_path + self.dima_common_part_of_logical_id
        pending_result_id = self._search_result(logical_id=pending_logical_id)

        if not pending_result_id:
            return self._create_new_result(test_cfg_path=test_cfg_path, test_case_id=test_case_id, logical_id=pending_logical_id, desc=text, status=status), 'created'

        body = '''
            <Result>
                <Title><![CDATA[Result {test_cfg_path}]]></Title>
                <Description><![CDATA[{desc}]]></Description>
                <ID xlink:href="http://{url}/xml/{result_id}/entity.svc">{result_id}</ID>
                <LogicalID><![CDATA[{logical_id}]]></LogicalID>
                <WriteAccess>member</WriteAccess>
                <ListFieldValue multi-value="true">
                    <FieldName><![CDATA[ Software Version ]]></FieldName>
                    <Value><![CDATA[ {mercury_version} ]]></Value>
                </ListFieldValue>
                <Status>{status}</Status>
                <ConfigID xlink:href="http://{url}/xml/{conf_id}/entity.svc">{conf_id}</ConfigID>
                <CaseID xlink:href="http://{url}/xml/{test_case_id}/entity.svc">{test_case_id}</CaseID>
            </Result>
        '''.format(test_cfg_path=test_cfg_path, url=self.tims_url, desc=text, status=status, mercury_version=self.gerrit_tag,
                   test_case_id=test_case_id, logical_id=pending_logical_id, result_id=pending_result_id, conf_id=self.conf_id)

        ans = self._api_post(operation=self._OPERATION_UPDATE, body=body)
        return ans.split('</ID>')[0].rsplit('>', 1)[-1], 'updated'

    def _create_new_result(self, test_cfg_path, test_case_id, logical_id, desc, status):
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
                <CaseID xlink:href="http://{url}/xml/{test_case_id}/entity.svc">{test_case_id}</CaseID>
                <ConfigID xlink:href="http://{url}/xml/{conf_id}/entity.svc">{conf_id}</ConfigID>

        </Result>
        '''.format(test_cfg_path=test_cfg_path, url=self.tims_url, test_case_id=test_case_id, logical_id=logical_id, description=desc, mercury_version=self.gerrit_tag, status=status, conf_id=self.conf_id)

        ans = str(self._api_post(operation=self._OPERATION_ENTITY, body=body))
        return ans.split('</ID>')[0].rsplit('>', 1)[-1]

    def publish(self, tc):
        url_tmpl = 'http://tims/warp.cmd?ent={}'
        try:
            if tc.tcr is None:
                tims_id, up_or_cr = self._create_update_test_case(test_case=tc)
                tc.set_tims_info(tims_id=tims_id, url_tmpl=url_tmpl)
                tc.log(up_or_cr)
            else:
                tims_id, up_or_cr = self._create_update_result(test_cfg_path=tc.path, test_case_id=tc.tims_id, text=tc.tcr.text, status=tc.tcr.status)
                tc.tcr.tims_url = url_tmpl.format(tims_id)
                tc.tcr.log(up_or_cr)
        except Exception:
            self.log_exception()

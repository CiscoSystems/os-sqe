import unittest
from lab.with_log import WithLogMixIn
from lab.with_config import WithConfig


class Tims(WithLogMixIn, WithConfig):
    _OPERATION_ENTITY = 'entity'
    _OPERATION_UPDATE = 'update'
    _OPERATION_SEARCH = 'search'

    def __init__(self, version):
        import getpass
        import json       
        import os
        import requests

        cfg_dic = json.loads(requests.get(url=self.CONFIGS_REPO_URL + '/tims.json').text)

        self.tims_project_id = cfg_dic['tims']['project_id']
        self.tims_db_name = cfg_dic['tims']['db_name']
        self.tims_folders = cfg_dic['tims']['folders']

        self.version = version

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
        self.header = '<Tims\n\txsi:schemaLocation="http://tims.cisco.com/namespace http://tims.cisco.com/xsd/Tims.xsd"\n\txmlns="http://tims.cisco.com/namespace"\n\txmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n\t' + \
                      'xmlns:xlink="http://www.w3.org/1999/xlink">\n\t<Credential user="{user}" token="{auth_token}"/>\n\t'.format(user=username, auth_token=token)
        self.footer = '\n</Tims>\n'

    def __repr__(self):
        return u'TIMS'

    def post(self, url, data):
        import requests

        r = requests.post(url, data)
        self.check(r)
        return r.content

    def get(self, url):
        import requests

        r = requests.get(url)
        self.check(r)
        return r.content

    def check(self, r):
        if 'Error' in r.content:
            raise RuntimeError('{}: {} error {}'.format(self, r.request.url, r.content.split('Error')[1]))

    def search_by_logical_id(self, logical_id, what):
        data = self.header + '''<Search scope="project" root="{}" entity="{}" casesensitive="true">
                                    <TextCriterion operator="is">
                                        <FieldName><![CDATA[Logical ID]]></FieldName>
                                        <Value><![CDATA[{}]]></Value>
                                    </TextCriterion>
                                </Search>'''.format(self.tims_project_id, what, logical_id) + self.footer

        xml = self.post('http://tims.cisco.com/xml/{}/search.svc'.format(self.tims_project_id), data=data)  # http://wwwin-ces.cisco.com/rtis/tims/learning/xml/apiref/search.shtml
        return xml.split('</SearchHit>')[0].rsplit('>', 1)[-1] if 'SearchHit' in xml else ''

    def create_update_test_case(self, tc):
        tc_id = self.search_by_logical_id(logical_id=tc.unique_id, what='case')
        id_str = '<ID xlink:href="http://tims.cisco.com/xml/{0}/entity.svc">{0}</ID>'.format(tc_id) if tc_id else ''
        desc = 'actual config:\n' + tc.body_text + '\nurl:\nhttps://raw.githubusercontent.com/CiscoSystems/os-sqe/master/configs/ha/{}\n'.format(tc.path)

        data = self.header + '''<Case>
                                    <Title><![CDATA[{title}]]></Title>
                                    <Description><![CDATA[{desc}]]>
                                    </Description>
                                    <LogicalID>{log_id}</LogicalID>
                                    {id_str}
                                    <FolderID xlink:href="http://tims.cisco.com/xml/{folder_id}/entity.svc">{folder_id}</FolderID>
                                </Case>'''.format(title=tc.title, desc=desc, log_id=tc.unique_id, id_str=id_str, folder_id=self.tims_folders[tc.folder]) + self.footer

        xml = self.post(url='http://tims.cisco.com/xml/{}/update.svc'.format(self.tims_project_id), data=data)
        return xml.split('</ID>')[0].rsplit('>', 1)[-1]

    def create_update_result(self, tc_id, tc_unique_id, status, text):

        logical_id = tc_unique_id + '-' + self.version
        tcr_id = self.search_by_logical_id(logical_id=logical_id, what='result')

        id_str = '<ID xlink:href="http://tims.cisco.com/xml/{0}/entity.svc">{0}</ID>'.format(tcr_id) if tcr_id else ''
        data = self.header + '''<Result>
                                    <Title><![CDATA[for {version}]]></Title>
                                    <Description><![CDATA[{desc}]]></Description>
                                    <LogicalID>{logical_id}</LogicalID>
                                    {id_str}
                                    <ListFieldValue multi-value="false">
                                        <FieldName><![CDATA[ Software Version ]]></FieldName>
                                        <Value><![CDATA[ {version} ]]></Value>
                                    </ListFieldValue>
                                    <Status>{status}</Status>
                                    <CaseID xlink:href="http://tims.cisco.com/xml/{tc_id}/entity.svc">{tc_id}</CaseID>
                                </Result>'''.format(logical_id=logical_id, id_str=id_str, desc=text, status=status, version=self.version, tc_id=tc_id) + self.footer

        xml = self.post(url='http://tims.cisco.com/xml/{}/update.svc'.format(self.tims_project_id), data=data)
        return xml.split('</ID>')[0].rsplit('>', 1)[-1]

    def publish_tcr(self, tc, tcr):
        url_tmpl = 'http://tims/warp.cmd?ent='
        try:
            tc_id = self.create_update_test_case(tc=tc)
            tcr_id = self.create_update_result(tc_id=tc_id, tc_unique_id=tc.unique_id, status=tcr.status, text=tcr.text)
            self.log('<{}|{}>: <{}|{}> {}'.format(url_tmpl + tc_id, tc.path, url_tmpl + tcr_id, tcr.status, tcr.text))
            return url_tmpl + tcr_id
        except RuntimeError:
            self.log_exception()


class TestTims(unittest.TestCase):
    def setUp(self):
        from lab.test_case import TestCase, TestCaseResult

        self.tims = Tims(version='2.2.5(11577)VTS')
        self.tc = TestCase(path='all01-containers-ctl-reboot.yaml', is_debug=True, is_noclean=False, cloud=None)
        self.tcr = TestCaseResult(tc=self.tc)
        self.tcr.status = self.tcr.FAILED
        self.tcr.text = 'run to test TIMS from tims.py'

    def test_publish_tcr(self):
        self.tims.publish_tcr(tc=self.tc, tcr=self.tcr)

    def test_create_update_test_case(self):
        self.tims.create_update_test_case(tc=self.tc)

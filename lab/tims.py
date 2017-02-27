from lab.with_log import WithLogMixIn


class Tims(WithLogMixIn):
    FOLDERS = {'HIGH AVAILABILITY': 'Tcbr1841f', 'NEGATIVE': 'Tcbr1979f', 'PERFOMANCE AND SCALE': 'Tcbr1840f'}
    TOKENS = {'kshileev': '0000003933000000000D450000000000',
              'nfedotov': '26520000006G00005F42000077044G47',
              'dratushn': '000000525F7G007900000000006G4700',
              'ymorkovn': '6B02004H0000005600003B0000000000'}

    TIMS_PROJECT_ID = 'Tcbr1p'

    _OPERATION_ENTITY = 'entity'
    _OPERATION_UPDATE = 'update'
    _OPERATION_SEARCH = 'search'

    def __init__(self):
        import getpass
        import os

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
            return None
        else:
            data = self._xml_tims_wrapper.format(body=body)
            response = requests.post("http://tims.cisco.com/xml/{}/{}.svc".format(self.TIMS_PROJECT_ID, operation), data=data)
            if u"Error" in response.content.decode():
                raise RuntimeError(response.content)
            return response.content

    def publish_tests_to_tims(self):
        from lab.with_config import WithConfig

        available_tc = WithConfig.ls_configs(directory='ha')
        test_cfg_pathes = sorted(filter(lambda x: 'tc-vts' in x, available_tc))

        test_case_template = '''
        <Case>
            <Title><![CDATA[ {test_name} ]]></Title>
            <Description><![CDATA[{description}]]></Description>
            <LogicalID>{logical_id}</LogicalID>
            <WriteAccess>member</WriteAccess>
            <ProjectID xlink:href="http://tims.cisco.com/xml/{project_id}/project.svc">{project_id}</ProjectID>
            <DatabaseID xlink:href="http://tims.cisco.com/xml/NFVICLOUDINFRA/database.svc">NFVICLOUDINFRA</DatabaseID>
            <FolderID xlink:href="http://tims.cisco.com/xml/{folder_id}/entity.svc">{folder_id}</FolderID>
        </Case>
        '''

        body = ''
        for test_cfg_path in test_cfg_pathes:
            cfg_body = WithConfig.read_config_from_file(config_path=test_cfg_path, directory='ha', is_as_string=True)

            folder_name = None
            test_name = ' '.join(test_cfg_path.strip('.yaml').split('-')[2:])

            for d in WithConfig.read_config_from_file(config_path=test_cfg_path, directory='ha'):
                folder_name = d.get('Folder', folder_name)

            if not folder_name:
                raise ValueError('test {} does not specify - Folder: {}'.format(test_cfg_path, self.FOLDERS.keys()))

            try:
                folder_id = self.FOLDERS[folder_name]
            except KeyError:
                raise ValueError('test {} specifies wrong Folder {}, possible values {}'.format(test_cfg_path, folder_name, self.FOLDERS.keys()))

            description = 'This is the configuration actually used in testing:\n' + cfg_body + '\nuploaded from <a href="https://raw.githubusercontent.com/CiscoSystems/os-sqe/master/configs/ha/{}">'.format(test_cfg_path)
            body += test_case_template.format(test_name=test_name, logical_id=test_cfg_path, description=description, folder_id=folder_id, project_id=self.TIMS_PROJECT_ID)

        self._api_post(operation=self._OPERATION_UPDATE, body=body)

    def publish_result_to_tims(self, test_cfg_path, mercury_version, lab, results):
        import json

        result_template = '''
        <Result>
                <Title><![CDATA[Result for {test_cfg_path}]]></Title>
                <Description><![CDATA[{description}]]></Description>
                <Owner>
                        <UserID>kshileev</UserID>
                </Owner>
                <ListFieldValue multi-value="true">
                    <FieldName><![CDATA[ Software Version ]]></FieldName>
                    <Value><![CDATA[ {mercury_version} ]]></Value>
                </ListFieldValue>

                <Status>{status}</Status>

                <CaseLookup>
                        <TextFieldValue searchoperator="is">
                                <FieldName>Logical ID</FieldName>
                                <Value>{test_cfg_path}</Value>
                        </TextFieldValue>
                </CaseLookup>
                <ConfigLookup>
                        <TextFieldValue searchoperator="is">
                                <FieldName>Logical ID</FieldName>
                                <Value>{lab_id}</Value>
                        </TextFieldValue>
                </ConfigLookup>
        </Result>
        '''

        fixed_dima_template = '''
            <Result>
                <Title><![CDATA[Result for {test_cfg_path}]]></Title>
                <ID xlink:href="http://tims.cisco.com/xml/{result_id}/entity.svc">{result_id}</ID>
                <Description><![CDATA[{description}]]></Description>
                <LogicalID><![CDATA[{test_cfg_path}:{mercury_version}]]></LogicalID>
                <Owner>
                        <UserID>kshileev</UserID>
                </Owner>
                <WriteAccess>member</WriteAccess>
                <ListFieldValue multi-value="true">
                    <FieldName><![CDATA[ Software Version ]]></FieldName>
                    <Value><![CDATA[ {mercury_version} ]]></Value>
                </ListFieldValue>
                <Status>{status}</Status>
            </Result>
        '''

        search_by_logical_id = """
            <Search scope="project" root="{project_id}" entity="result" casesensitive="true">
               <TextCriterion operator="is">
                    <FieldName><![CDATA[Logical ID]]></FieldName>
                    <Value><![CDATA[{test_cfg_path}:{mercury_version}]]></Value>
                </TextCriterion>
            </Search>
        """

        print("Results: {0}".format(results))
        status = 'passed' if sum([len(x.get('exceptions', [])) for x in results]) == 0 else 'failed'
        description = json.dumps(results, indent=4)
        body = result_template.format(test_cfg_path=test_cfg_path, description=description, mercury_version=mercury_version, status=status, lab_id=lab)

        ans = self._api_post(operation=self._OPERATION_ENTITY, body=body)
        if ans:
            tims_report_url = 'http://tims/warp.cmd?ent={}'.format(ans.split('</ID>')[0].rsplit('>', 1)[-1])

            search_result = self._api_post(operation=self._OPERATION_SEARCH, body=search_by_logical_id.format(project_id=self.TIMS_PROJECT_ID, test_cfg_path=test_cfg_path, mercury_version=mercury_version))
            resutl_id = search_result.split('</SearchHit>')[0].rsplit('>', 1)[-1]
            if resutl_id.startswith('Tcbr'):
                body_dima = fixed_dima_template.format(test_cfg_path=test_cfg_path, description=description, mercury_version=mercury_version, status=status, lab_id=lab, result_id=resutl_id)
                self._api_post(operation=self._OPERATION_UPDATE, body=body_dima)
        else:
            tims_report_url = 'and not reported to tims since user not known'

        self.log_to_slack(message='{} {}: {} {} {}'.format(lab, mercury_version, test_cfg_path, status.upper(), tims_report_url))

    def simulate(self):
        from lab.with_config import WithConfig

        mercury_version, vts_version = '0022', 'vts'

        available_tc = WithConfig.ls_configs(directory='ha')

        for test_cfg_path in sorted(filter(lambda x: 'tc-vts' in x, available_tc)):
            results = [{'name': 'worker=ParallelWorker', 'input': 'generic input', 'exceptions': []}]
            self.publish_result_to_tims(test_cfg_path=test_cfg_path, mercury_version=mercury_version, lab='FAKE', results=results)

if __name__ == '__main__':
    t = Tims()
    t.simulate()

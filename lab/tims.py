class Tims(object):
    FOLDERS = {'HIGH AVAILABILITY': 'Tcbr1841f', 'NEGATIVE': 'Tcbr1979f'}
    TIMS_PROJECT_ID = 'Tcbr1p'

    _OPERATION_ENTITY = 'entity'
    _OPERATION_UPDATE = 'update'

    def __init__(self):
        import os

        self._username = os.getenv('USER')

    def _api_post(self, operation, body):
        import requests

        xml_tims_wrapper = '''
<Tims xmlns="http://tims.cisco.com/namespace" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xlink="http://www.w3.org/1999/xlink" xsi:schemaLocation="http://tims.cisco.com/namespace http://tims.cisco.com/xsd/Tims.xsd">
<Credential user="kshileev" token="0000003933000000000D450000000000"/>
{body}
</Tims>

'''
        data = xml_tims_wrapper.format(body=body)
        response = requests.post("http://tims.cisco.com/xml/{}/{}.svc".format(self.TIMS_PROJECT_ID, operation), data=data)
        if u"Error" in response.content.decode():
            raise RuntimeError(response.content)
        return response.content

    def publish_tests_to_tims(self):
        from lab import with_config

        available_tc = with_config.ls_configs(directory='ha')
        test_cfg_pathes = sorted(filter(lambda x: 'tc-vts' in x, available_tc))

        test_case_template = '''
        <Case>
            <Title><![CDATA[ {test_name} ]]></Title>
            <Description><![CDATA[{description}]]></Description>
            <LogicalID>{logical_id}</LogicalID>
            <Owner>
                <UserID>{username}</UserID>
                <Email>{username}@cisco.com</Email>
            </Owner>
            <WriteAccess>member</WriteAccess>
            <ProjectID xlink:href="http://tims.cisco.com/xml/{project_id}/project.svc">{project_id}</ProjectID>
            <DatabaseID xlink:href="http://tims.cisco.com/xml/NFVICLOUDINFRA/database.svc">NFVICLOUDINFRA</DatabaseID>
            <FolderID xlink:href="http://tims.cisco.com/xml/{folder_id}/entity.svc">{folder_id}</FolderID>
        </Case>
        '''

        body = ''
        for test_cfg_path in test_cfg_pathes:
            cfg_body = with_config.read_config_from_file(config_path=test_cfg_path, directory='ha', is_as_string=True)

            folder_name = None
            test_name = ' '.join(test_cfg_path.strip('.yaml').split('-')[2:])

            for d in with_config.read_config_from_file(config_path=test_cfg_path, directory='ha'):
                folder_name = d.get('Folder', folder_name)

            if not folder_name:
                raise ValueError('test {} does not specify - Folder: {}'.format(test_cfg_path, self.FOLDERS.keys()))

            try:
                folder_id = self.FOLDERS[folder_name]
            except KeyError:
                raise ValueError('test {} specifies wrong Folder, possible values {}'.format(test_cfg_path, self.FOLDERS.keys()))

            description = 'This is the configuration actually used in testing:\n' + cfg_body + '\nuploaded from <a href="https://raw.githubusercontent.com/CiscoSystems/os-sqe/master/configs/ha/{}">'.format(test_cfg_path)
            body += test_case_template.format(username=self._username, test_name=test_name, logical_id=test_cfg_path, description=description, folder_id=folder_id, project_id=self.TIMS_PROJECT_ID)

        self._api_post(operation=self._OPERATION_UPDATE, body=body)

        for test_cfg_path in test_cfg_pathes:
            self.publish_result_to_tims(test_cfg_path=test_cfg_path, mercury_version='1.0.9', vts_version='LATEST', n_exceptions=-10, lab='g7-2')

    def publish_result_to_tims(self, test_cfg_path, mercury_version, vts_version, lab, n_exceptions):
        description = 'VTS version: {} Mercury version: {} number of exceptions {}'.format(vts_version, mercury_version, n_exceptions)
        if n_exceptions > 0:
            status = 'failed'
        elif n_exceptions == 0:
            status = 'passed'
        else:
            status = 'pending'

        result_template = '''
        <Result>
                <Title><![CDATA[Result for {test_cfg_path}]]></Title>
                <Description><![CDATA[{description}]]></Description>
                <Owner>
                        <UserID>{username}</UserID>
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
                                <Value>{lab}</Value>
                        </TextFieldValue>
                </ConfigLookup>
        </Result>
        '''

        body = result_template.format(username=self._username, test_cfg_path=test_cfg_path, description=description, mercury_version=mercury_version, status=status, lab=lab)
        self._api_post(operation=self._OPERATION_ENTITY, body=body)

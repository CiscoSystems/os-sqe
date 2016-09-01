TEST_CASE_TEMPLATE = """
<Tims xmlns="http://tims.cisco.com/namespace" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xlink="http://www.w3.org/1999/xlink" xsi:schemaLocation="http://tims.cisco.com/namespace http://tims.cisco.com/xsd/Tims.xsd">
<Credential user="dratushn" token="000000525F7G007900000000006G4700"/>
<Case>
<Title><![CDATA[ {title} ]]></Title>
 <Description><![CDATA[{description}]]></Description>
        <Owner>
            <UserID>{username}</UserID>
            <FirstName>CiscoSystems</FirstName>
            <LastName>os-sqe</LastName>
            <Email>{username}@cisco.com</Email>
        </Owner>
<WriteAccess>member</WriteAccess>
<Created>{created}</Created>
<Modified>{created}</Modified>
<ProjectID xlink:href="http://tims.cisco.com/xml/{project_id}/project.svc">{project_id}</ProjectID>
<DatabaseID xlink:href="http://tims.cisco.com/xml/NFVICLOUDINFRA/database.svc">NFVICLOUDINFRA</DatabaseID>
<FolderID xlink:href="http://tims.cisco.com/xml/{folder_id}/entity.svc">{folder_id}</FolderID>
</Case>
<Timestamp>{created}</Timestamp>
<ExecutionTime>0.00</ExecutionTime>
</Tims>
"""


class Tims(object):
    FOLDERS = {'HIGH AVAILABILITY': 'Tcbr1841f', 'NEGATIVE': 'Tcbr1979f'}
    TIMS_PROJECT_ID = 'Tcbr1p'

    def __init__(self):
        import os

        self._username = os.getenv('USER')

    def _api_post(self, project_id, entity_or_search, data):
        import requests

        response = requests.post("http://tims.cisco.com/xml/{}/{}.svc".format(project_id, entity_or_search), data=data)
        if u"Error" in response.content.decode():
            raise RuntimeError(response.content)
        return response.content

    def create_or_update_test_case(self, folder_id, test_name, test_description):
        import datetime

        data = TEST_CASE_TEMPLATE.format(username=self._username, created=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"), title=test_name, description=test_description,
                                         folder_id=folder_id, project_id=self.TIMS_PROJECT_ID)
        return self._api_post(project_id=self.TIMS_PROJECT_ID, entity_or_search='entity', data=data)

    def publish_tests_to_tims(self):
        from lab import with_config

        available_tc = with_config.ls_configs(directory='ha')
        tests = sorted(filter(lambda x: 'tc-vts' in x, available_tc))

        for test in tests:
            body = with_config.read_config_from_file(config_path=test, directory='ha', is_as_string=True)

            folder_name = None
            test_name = ' '.join(test.strip('.yaml').split('-')[2:])

            for d in with_config.read_config_from_file(config_path=test, directory='ha'):
                folder_name = d.get('Folder', folder_name)

            if not folder_name:
                raise ValueError('test {} does not specify - Folder: {}'.format(test, self.FOLDERS.keys()))

            try:
                folder_id = self.FOLDERS[folder_name]
            except KeyError:
                raise ValueError('test {} specifies wrong Folder, possible values {}'.format(test, self.FOLDERS.keys()))

            description = 'This is the configuration actually used in testing:\n' + body + '\nuploaded from https://raw.githubusercontent.com/CiscoSystems/os-sqe/master/configs/ha/{}'.format(test)
            self.create_or_update_test_case(folder_id=folder_id, test_name=test_name, test_description=description)

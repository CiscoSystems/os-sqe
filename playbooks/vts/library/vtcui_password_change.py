def main():
    import json
    import requests

    result = {}
    module = AnsibleModule(
        argument_spec = dict(
            vtc_ip=dict(required=True, type='str'),
            user=dict(required=True, type='str'),
            password=dict(default=None, type='str'),
            new_password=dict(default=None, type='str')
        ),
        supports_check_mode=True
    )

    vtc_ip = module.params['vtc_ip']
    user = module.params['user']
    password = module.params['password']
    new_password = module.params['new_password']

    api_url = lambda r: 'https://{ip}:{port}/VTS/{resource}'.format(ip=vtc_ip, port=8443, resource=r)

    session = requests.Session()
    auth = session.post(api_url('j_spring_security_check'), data={'j_username': user, 'j_password': password, 'Submit': 'Login'}, verify=False)
    if 'Invalid username or passphrase' in auth.text:
        result['changed'] = False
        result['stderr'] = auth.text

    java_script_servlet = session.get(api_url('JavaScriptServlet'), verify=False)
    owasp_csrftoken = ''.join(re.findall('OWASP_CSRFTOKEN", "(.*?)", requestPageTokens', java_script_servlet.text))
    if not owasp_csrftoken:
        result['changed'] = False
        result['stdout'] = java_script_servlet.text
        result['stderr'] = 'OWASP_CSRFTOKEN token has not been found'

    response = session.put(api_url('rs/ncs/user?updatePassword=true&isEnforcePassword=true'),
                           data=json.dumps({'resource': {'user': {'user_name': user, 'password': new_password, 'currentPassword': password}}}),
                           headers={'OWASP_CSRFTOKEN': owasp_csrftoken,
                                    'X-Requested-With': 'OWASP CSRFGuard Project',
                                    'Accept': 'application/json, text/plain, */*',
                                    'Accept-Encoding': 'gzip, deflate, sdch, br',
                                    'Content-Type': 'application/json;charset=UTF-8'})

    if response.status_code == 200 and 'Error report' not in response.text:
        result['changed'] = True
        result['stdout'] = response.text
    else:
        result['changed'] = False
        result['stderr'] = response.text

    module.exit_json(**result)

# import module snippets
from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()

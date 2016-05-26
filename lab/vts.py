from lab.lab_node import LabNode


class Vts(LabNode):
    def _rest_api(self, resource, params=None):
        import requests

        # requests.packages.urllib3.disable_warnings() # Suppressing warning due to self-signed certificate

        url = 'https://{ip}/{resource}'.format(ip=self._ip, resource=resource)
        auth = (self._username, self._password)
        headers = {'Accept': 'application/vnd.yang.data+json'}
        try:
            res = requests.get(url, auth=auth, headers=headers, params=params, timeout=10, verify=False)
            return res
        except requests.exceptions.ConnectionError:
            pass

    def get_vni_pool(self):
        ans = self._rest_api(resource='/api/running/resource-pools/vni-pool/vnipool')

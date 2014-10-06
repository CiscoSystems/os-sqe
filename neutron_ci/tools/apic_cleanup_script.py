import requests
import json
import time
import argparse

APIC_CODE_FORBIDDEN = str(requests.codes.forbidden)

class ApicSession(object):

    """Manages a session with the APIC."""

    def __init__(self, host, port, usr, pwd, ssl):
        protocol = ssl and 'https' or 'http'
        self.api_base = '%s://%s:%s/api' % (protocol, host, port)
        self.session = requests.Session()
        self.session_deadline = 0
        self.session_timeout = 0
        self.cookie = {}

        # Log in
        self.authentication = None
        self.username = None
        self.password = None
        if usr and pwd:
            self.login(usr, pwd)

    @staticmethod
    def _make_data(key, **attrs):
        """Build the body for a msg out of a key and some attributes."""
        return json.dumps({key: {'attributes': attrs}})

    def _api_url(self, api):
        """Create the URL for a generic API."""
        return '%s/%s.json' % (self.api_base, api)

    def _mo_url(self, mo, *args):
        """Create a URL for a MO lookup by DN."""
        dn = mo.dn(*args)
        return '%s/mo/%s.json' % (self.api_base, dn)

    def _qry_url(self, mo):
        """Create a URL for a query lookup by MO class."""
        return '%s/class/%s.json' % (self.api_base, mo.klass_name)

    def _send(self, request, url, data=None, refreshed=None):
        """Send a request and process the response."""
        if self.api_base not in url:
            url = self.api_base + '/' + url
        if data is None:
            response = request(url, cookies=self.cookie)
        else:
            response = request(url, data=data, cookies=self.cookie)
        if response is None:
            raise Exception('No response from APIC in %s' % url)
        # Every request refreshes the timeout
        self.session_deadline = time.time() + self.session_timeout
        if data is None:
            request_str = url
        else:
            request_str = '%s, data=%s' % (url, data)
            print "data = %s"
        # imdata is where the APIC returns the useful information
        imdata = response.json().get('imdata')
        print "Response: %s" % imdata
        if response.status_code != requests.codes.ok:
            try:
                err_code = imdata[0]['error']['attributes']['code']
                err_text = imdata[0]['error']['attributes']['text']
            except (IndexError, KeyError):
                err_code = '[code for APIC error not found]'
                err_text = '[text for APIC error not found]'
            # If invalid token then re-login and retry once
            if (not refreshed and err_code == APIC_CODE_FORBIDDEN and
                    err_text.lower().startswith('token was invalid')):
                self.login()
                return self._send(request, url, data=data, refreshed=True)
            raise Exception('Apic response not OK:\n %s\n %s\n %s\n %s\n %s' %
                            (request_str, response.status_code,
                             response.reason, err_text, err_code))
        return imdata

    # Session management

    def _save_cookie(self, request, response):
        """Save the session cookie and its expiration time."""
        imdata = response.json().get('imdata')
        if response.status_code == requests.codes.ok:
            attributes = imdata[0]['aaaLogin']['attributes']
            try:
                self.cookie = {'APIC-Cookie': attributes['token']}
            except KeyError:
                raise Exception('No cookie in APIC login response')
            timeout = int(attributes['refreshTimeoutSeconds'])
            print "APIC session will expire in %d seconds" % timeout
            # Give ourselves a few seconds to refresh before timing out
            self.session_timeout = timeout - 5
            self.session_deadline = time.time() + self.session_timeout
        else:
            attributes = imdata[0]['error']['attributes']
        return attributes

    def login(self, usr=None, pwd=None):
        """Log in to controller. Save user name and authentication."""
        usr = usr or self.username
        pwd = pwd or self.password
        name_pwd = self._make_data('aaaUser', name=usr, pwd=pwd)
        url = self._api_url('aaaLogin')
        try:
            response = self.session.post(url, data=name_pwd, timeout=10.0, verify=False)
        except requests.exceptions.Timeout:
            raise Exception('No response from APIC: %s ' % url)
        attributes = self._save_cookie('aaaLogin', response)
        if response.status_code == requests.codes.ok:
            self.username = usr
            self.password = pwd
            self.authentication = attributes
        else:
            self.authentication = None
            raise Exception('Apic response not OK:\n %s\n %s\n %s\n %s\n %s' %
                            (url, response.status_code, response.reason,
                             attributes['text'], attributes['code']))

    def refresh(self):
        """Called when a session has timed out or almost timed out."""
        url = self._api_url('aaaRefresh')
        response = self.session.get(url, cookies=self.cookie)
        attributes = self._save_cookie('aaaRefresh', response)
        if response.status_code == requests.codes.ok:
            # We refreshed before the session timed out.
            self.authentication = attributes
        else:
            err_code = attributes['code']
            err_text = attributes['text']
            if (err_code == APIC_CODE_FORBIDDEN and
                    err_text.lower().startswith('token was invalid')):
                # This means the token timed out, so log in again.
                print "APIC session timed-out, logging in again."
                self.login()
            else:
                self.authentication = None
                raise Exception('Login failed')

    def logout(self):
        """End session with controller."""
        if not self.username:
            self.authentication = None
        if self.authentication:
            data = self._make_data('aaaUser', name=self.username)
            self.post_data('aaaLogout', data=data)
        self.authentication = None

    def GET(self, url, data=None):
        return self._send(self.session.get, url, data=data)

    def POST(self, url, data=None):
        return self._send(self.session.post, url, data=data)

    def DELETE(self, url, data=None):
        return self._send(self.session.delete, url, data=data)

    def delete_class(self, klass):
        nodes = apic_session.GET('node/class/%s.json'%klass)
        for node in nodes:
            dn = node[klass]['attributes']['dn']
            apic_session.DELETE('node/mo/' + '/' + dn + '.json')

parser = argparse.ArgumentParser(description='Cleans APIC infra profiles')
parser.add_argument('apic_ip', help='APIC ip address')
parser.add_argument('apic_port', help='APIC port')
parser.add_argument('apic_username', help='APIC username')
parser.add_argument('apic_password', help='APIC password')
parser.add_argument('--ssl', help='Wether to use SSL or not', default=False)

if __name__ == "__main__":
    args = parser.parse_args()
    apic_session = ApicSession(args.apic_ip, args.apic_port,
                               args.apic_username,
                               args.apic_password, args.ssl)
    apic_session.login()
    apic_session.delete_class('infraNodeP')
    apic_session.delete_class('infraAccPortP')

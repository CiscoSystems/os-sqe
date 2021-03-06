from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class Server(WithConfig, WithLogMixIn):
    N_CONNECTION_ATTEMPTS = 200

    def __init__(self, ip, username, password):
        self._tmp_dir_exists = False
        self._package_manager = None
        self.ip, self.username, self.password = ip, username, password

    def __repr__(self):
        return ('sshpass -p ' + self.password + ' ' if self.password else '') + 'ssh {}@{}'.format(self.username, self.ip)

    def exe(self, cmd, in_dir='.', is_warn_only=False, n_attempts=N_CONNECTION_ATTEMPTS):
        from fabric.api import run, settings, cd, hide

        if str(self.ip) in ['localhost', '127.0.0.1']:
            return self._exe_local(cmd, in_directory=in_dir, warn_only=is_warn_only)

        try:
            with settings(hide('warnings', 'aborts', 'output', 'running'),
                          abort_on_prompts=True,
                          disable_known_hosts=True,
                          connection_attempts=n_attempts,
                          warn_only=is_warn_only,
                          host_string=self.username + '@' + self.ip,
                          password=self.password,
                          key=None if self.password else self.PRIVATE_KEY), cd(in_dir):
                self.log_debug(cmd + ' running...')
                res = run(cmd)
                if res.failed and not is_warn_only:
                    self.log_debug('fail: {}'.format(res))
                    raise RuntimeError(res.stderr)
                self.log_debug(cmd + ' answer:\n' + res)
                return res
        except SystemExit as ex:
            if 'Needed to prompt' in ex.message:
                raise ValueError('{}: username/password wrong'.format(self))
            else:
                raise RuntimeError('{} {}: \n {}'.format(self, cmd, ex.message))

    def get_package_manager(self):
        if not self._package_manager:
            possible_packages = ['apt-get', 'dnf', 'yum']
            for x in possible_packages:
                if self.exe(cmd='whereis {0}'.format(x)) != x + ':':
                    self._package_manager = x
                    break
            if not self._package_manager:
                raise RuntimeError('do not know which package manager to use: neither of {0} found'.format(possible_packages))
        return self._package_manager

    @staticmethod
    def _exe_local(command, in_directory='.', warn_only=False):
        from fabric.api import local, settings, lcd

        if in_directory != '.':
            local('mkdir -p {0}'.format(in_directory))
        with settings(warn_only=warn_only):
            with lcd(in_directory):
                return local(command=command, capture=True)

    def check_or_install_packages(self, package_names):
        pm = self.get_package_manager()

        for package_name in package_names.split():
            if self.exe(cmd='whereis {0}'.format(package_name)) == package_name + ':':
                self.exe(cmd='sudo {0} install -y {1}'.format(pm, package_names))

    def create_user(self, username, public_key, private_key):
        tmp_password = 'password'

        a = 'grep {1} /etc/passwd || openssl passwd -crypt {0} | while read p; do adduser -p $p {1}; echo "{1} ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/{1}; '.format(tmp_password, username)
        b = 'mkdir -p ~{0}/.ssh ; chmod 700 ~{0}/.ssh ; cp .ssh/* ~{0}/.ssh ; cp openstack-configs/{{*.yaml,openrc}} ~{0}/ ; chown -R {0}.{0} ~{0}; done'.format(username)
        self.exe(cmd=a + b)

        self.username=username
        self.password=tmp_password

        # it's Local gitlab server key
        gitlab_public = 'wwwin-gitlab-sjc.cisco.com,10.22.31.77 ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBJZlfIFWs5/EaXGnR9oXp6mCtShpvO2zKGqJxNMvMJmixdkdW4oPjxYEYP+2tXKPorvh3Wweol82V3KOkB6VhLk='
        # private key is needed to commit to local github
        self.exe('echo "{}" > known_hosts ; echo "{}" > ~/aaa; cp ~/aaa authorized_keys; echo "{}" > sqe_private; chmod 600 *'.format(gitlab_public, public_key, private_key), in_dir='.ssh')
        self.exe('echo "Host *\n  StrictHostKeyChecking no\nUserKnownHostsFile=/dev/null\n" > .ssh/config; chmod 644 .ssh/config')  # ssh to controls and computes without prompts
        self.password = None
        self.log('Created user ' + username)

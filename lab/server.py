from lab.with_config import WithConfig
from lab.with_log import WithLogMixIn


class Server(WithConfig, WithLogMixIn):
    N_CONNECTION_ATTEMPTS = 200

    def __init__(self, ip, username, password):
        self._tmp_dir_exists = False
        self._package_manager = None
        self.ip, self.username, self.password = ip, username, password

    def __repr__(self):
        return 'Server {} {}/{}'.format(self.ip, self.username, self.password)

    def exe(self, cmd, in_dir='.', is_warn_only=False, n_attempts=N_CONNECTION_ATTEMPTS):
        from fabric.api import run, settings, cd

        if str(self.ip) in ['localhost', '127.0.0.1']:
            return self._exe_local(cmd, in_directory=in_dir, warn_only=is_warn_only)

        with settings(**self.construct_settings(is_warn_only=is_warn_only, n_attempts=n_attempts)), cd(in_dir):
            res = run(cmd)
            if res.failed and not is_warn_only:
                raise RuntimeError(res.stderr)
            return res

    def construct_settings(self, is_warn_only, n_attempts):
        env = {'host_string': self.username + '@' + self.ip,
               'disable_known_hosts': True, 'abort_on_prompts': True, 'connection_attempts': n_attempts, 'warn_only': is_warn_only}
        if self.password is None:
            env['key'] = self.PRIVATE_KEY
        else:
            env['password'] = self.password
        return env

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

    def file_append(self, file_path, data, in_directory='.', is_warn_only=False, n_attempts=N_CONNECTION_ATTEMPTS):
        from fabric.api import settings, cd
        from fabric.contrib import files
        from fabric.exceptions import NetworkError

        with settings(**self.construct_settings(is_warn_only=is_warn_only, n_attempts=n_attempts)):
            with cd(in_directory):
                try:
                    return files.append(file_path, data)
                except NetworkError:
                    if is_warn_only:
                        return ''
                    else:
                        raise

    def reboot(self, wait=300):
        """Reboot this server
        :param wait: wait for the server to come up
        """
        from fabric.api import reboot, settings

        with settings(**self.construct_settings(is_warn_only=True, n_attempts=self.N_CONNECTION_ATTEMPTS)):
            reboot(wait=wait)

    def put(self, local_path, remote_path, is_sudo):
        """Faced the normal fabric put to provide server details from the class
        :param local_path:
        :param remote_path:
        :param is_sudo:
        :return:
        """
        from fabric.api import put, settings

        with settings(**self.construct_settings(is_warn_only=False, n_attempts=self.N_CONNECTION_ATTEMPTS)):
            return put(local_path=local_path, remote_path=remote_path, use_sudo=is_sudo)

    def check_or_install_packages(self, package_names):
        pm = self.get_package_manager()

        for package_name in package_names.split():
            if self.exe(cmd='whereis {0}'.format(package_name)) == package_name + ':':
                self.exe(cmd='sudo {0} install -y {1}'.format(pm, package_names))

    def create_user(self, username, public_key):
        tmp_password = 'password'

        a = 'grep {1} /etc/passwd || openssl passwd -crypt {0} | while read p; do adduser -p $p {1}; echo "{1} ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/{1}; '.format(tmp_password, username)
        b = 'mkdir -p ~{0}/.ssh ; chmod 700 ~{0}/.ssh ; cp .ssh/* ~{0}/.ssh ; cp openstack-configs/{{*.yaml,openrc}} ~{0}/ ; chown -R {0}.{0} ~{0}; done'.format(username)
        self.exe(cmd=a + b)

        sqe = Server(ip=self.ip, username=username, password=tmp_password)
        gitlab_public = 'wwwin-gitlab-sjc.cisco.com,10.22.31.77 ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBJZlfIFWs5/EaXGnR9oXp6mCtShpvO2zKGqJxNMvMJmixdkdW4oPjxYEYP+2tXKPorvh3Wweol82V3KOkB6VhLk='
        sqe.exe('echo {} > .ssh/known_hosts ; echo "{}" > aaa; cp aaa .ssh/authorized_keys; chmod 600 .ssh/authorized_keys'.format(gitlab_public, public_key))  # after this point key access is ok

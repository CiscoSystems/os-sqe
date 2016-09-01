class WithLogMixIn(object):

    @staticmethod
    def log_to_artifact(name, body):
        from lab.with_config import open_artifact

        with open_artifact(name, 'w') as f:
            f.write(body)

    def _format_single_cmd_output(self, cmd, ans):
        n = 160
        return n * 'v' + '\n' + self.__repr__() + '> ' + cmd + '\n' + n * '^' + '\n' + ans + '\n' + n * '-' + '\n\n'

    @staticmethod
    def upload_artifacts_to_our_server():
        """Store $REPO/*.log and $REPO/artifacts/* on file storage server"""
        from lab.server import Server

        destination_dir = '/var/www/artifacts'
        server = Server(ip='172.29.173.233', username='localadmin', password='ubuntu')
        server.exe(command='mkdir -p {0}'.format(destination_dir))
        server.put(local_path='*.log', remote_path=destination_dir, is_sudo=False)
        server.put(local_path='artifacts/*', remote_path=destination_dir, is_sudo=False)

    @staticmethod
    def _form_log_grep_cmd(log_files, regex=None, minutes=0):
        """regex: 'string: some regexp to be used in grep, empty means all',
        'minutes': 'int: 10 -> filter out all messages older then 10 minutes ago, 0 means no filter'}
        """

        cmd = '[[ -n "$(ls {})" ]] && '.format(log_files)
        cmd += 'sed -n "/^$(date +%Y-%m-%d\ %H:%M --date="{min} min ago")/, /^$(date +%Y-%m-%d\ %H:%M)/p" '.format(min=minutes) if minutes else 'cat '
        cmd += log_files
        cmd += ' | grep ' + regex if regex else ''
        return cmd

    def log(self, message, level='info'):
        from lab.logger import lab_logger

        message = '{}: {}'.format(self, message)
        if level == 'info':
            lab_logger.info(message)
        elif level == 'warning':
            lab_logger.warning(message)
        elif level == 'exception':
            lab_logger.exception(message)
        else:
            raise RuntimeError('Specified "{}" logger level is not known'.format(level))

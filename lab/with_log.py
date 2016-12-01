class WithLogMixIn(object):

    @staticmethod
    def log_to_artifact(name, body):
        from lab.with_config import WithConfig

        with WithConfig.open_artifact(name, 'w') as f:
            f.write(body)

    def _format_single_cmd_output(self, cmd, ans, node=None):
        n = 200
        return '\n' + n * 'v' + '\n' + (node or str(self)) + '> ' + cmd + '\n' + n * '^' + '\n' + ans + '\n' + n * '-' + '\n\n'

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
    def _form_log_grep_cmd(log_files, regex, minutes=0):
        """regex: 'string: some regexp to be used in grep, empty means all',
        'minutes': 'int: 10 -> filter out all messages older then 10 minutes ago, 0 means no filter'}
        """

        cmd = "grep -r '{}' {} ".format(regex, log_files)
        cmd += 'sed -n "/^$(date +%Y-%m-%d\ %H:%M --date="{min} min ago")/, /^$(date +%Y-%m-%d\ %H:%M)/p" '.format(min=minutes) if minutes else ''
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

    def log_to_slack(self, message):
        import requests
        import json

        data = json.dumps({"channel": "#autoreports", "username": "leeroy", "text": '{}: {}'.format(self, message)})
        requests.post(url='https://hooks.slack.com/services/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', data=data)
        self.log('{}'.format(message))

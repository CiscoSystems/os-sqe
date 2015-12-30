def start(lab, log, args):
    import os
    import datetime
    from fabric.api import settings
    from fabric.context_managers import cd, shell_env

    test = args['test']
    etime = args['etime']
    tempest_path = os.path.join(lab.director().temp_dir, 'tempest')
    git = args['git']
    branch = args.get('branch', 'proposed')
    tempest_config_dir = args.get('tempest_config_dir', '/etc/redhat-certification-openstack')

    # Create directory if it does not exist
    if lab.director().run('test -d {0}'.format(tempest_path), warn_only=True).return_code:
        lab.director().run('mkdir -p {0}'.format(tempest_path))

    # If there is no tempest yet run this scenario in the beginning of the test.
    # Set etime to smallest value to let it run once or so.
    with settings(command_timeout=60 * 5), cd(tempest_path):
        if lab.director().run('git status', warn_only=True).return_code > 0:
            lab.director().run('git init')
            lab.director().run('virtualenv venv')
        lab.director().run('git fetch {0} {1} && git checkout FETCH_HEAD'.format(git, branch))
        lab.director().run('source venv/bin/activate && pip install --upgrade setuptools funcsigs functools32 docutils jinja2 pytz UcsSdk')
        lab.director().run('source venv/bin/activate && pip install -r requirements.txt')
        lab.director().run('source venv/bin/activate && pip install -r test-requirements.txt')

    start_time = datetime.datetime.now()
    with cd(tempest_path), shell_env(TEMPEST_CONFIG_DIR=tempest_config_dir):
        lab.director().run('source venv/bin/activate && testr init')
        while (datetime.datetime.now() - start_time).seconds < etime:
            res = lab.director().run('source venv/bin/activate && testr run {0}'.format(test))
            log.info('Tempest run {0}, Result {1}'.format(test, res.return_code))

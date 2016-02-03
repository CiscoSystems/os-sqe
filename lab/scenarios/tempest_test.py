def start(lab, log, args):
    import os
    import datetime
    import time
    from fabric.api import settings
    from fabric.context_managers import cd

    test = args['test']
    tempest_path = os.path.join(lab.director().temp_dir, 'tempest')
    git = args['git']
    branch = args.get('branch', 'proposed')
    tempest_config_dir = args.get('tempest_config_dir', '/etc/redhat-certification-openstack')
    ramp_up_time = int(args.get('ramp_up_time', 1))

    lock_file = os.path.join(tempest_path, 'lock')

    time.sleep(ramp_up_time)

    # Create directory if it does not exist
    if lab.director().run('test -d {0}'.format(tempest_path), warn_only=True).return_code:
        lab.director().run('mkdir -p {0}'.format(tempest_path))

    # Wait if lock file exists
    start_time = datetime.datetime.now()
    while (datetime.datetime.now() - start_time).seconds < 60 * 5 and not lab.director().run('test -e {0}'.format(lock_file), warn_only=True).return_code:
        time.sleep(3)
    if not lab.director().run('test -e {0}'.format(lock_file), warn_only=True).return_code:
        raise Exception('Lock file [{0}] exists. Another scenario is working with the directory.'.format(lock_file))

    # If there is no tempest yet run this scenario in the beginning of the test.
    with settings(command_timeout=60 * 5), cd(tempest_path):
        if lab.director().run('git status', warn_only=True).return_code > 0:
            # Create lock file
            lab.director().run('touch {0}'.format(lock_file))
            # Clone tempest and install dependencies
            lab.director().run('git init')
            lab.director().run('virtualenv venv')
            lab.director().run('git fetch {0} {1} && git checkout FETCH_HEAD'.format(git, branch))
            lab.director().run('source venv/bin/activate && pip install --upgrade setuptools funcsigs functools32 docutils jinja2 pytz UcsSdk')
            lab.director().run('source venv/bin/activate && pip install -r requirements.txt')
            lab.director().run('source venv/bin/activate && pip install -r test-requirements.txt')
            lab.director().run('cp {tempest}/tempest.conf etc/'.format(tempest=tempest_config_dir))
            # Remove lock file
            lab.director().run('rm {0}'.format(lock_file))

    with cd(tempest_path):
        lab.director().run('source venv/bin/activate && testr init')
        res = lab.director().run('source venv/bin/activate && testr run {0}'.format(test), warn_only=True)
        log.info('run={0}, result={1}'.format(test, res.return_code))

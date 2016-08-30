def start(lab, log, args):
    from fabric.context_managers import shell_env

    grep_host = args.get('grep_host', 'overcloud-')

    statuses = {'up': 1, 'down': 0}

    server = lab.director()

    with shell_env(OS_AUTH_URL=lab.cloud.end_point, OS_USERNAME=lab.cloud.user, OS_PASSWORD=lab.cloud.password, OS_TENANT_NAME=lab.cloud.tenant):
        res = server.exe("nova service-list | grep {0} | awk '{{print $4 \" \" $6 \" \" $12}}'".format(grep_host), warn_only=True)
    results = [line.split() for line in res.split('\n')]
    msg = ' '.join(['{1}:{0}={2}'.format(r[0], r[1], statuses[r[2]]) for r in results])
    log.info('{1}'.format(grep_host, msg))


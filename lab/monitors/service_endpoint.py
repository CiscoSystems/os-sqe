def start(context, log, args):
    import time
    import requests

    from fabric.api import local

    # service type: compute, network, image etc.
    type = args['type']
    # adminURL / publicURL / internalURL
    url_type = args.get('url_type', 'publicURL')

    # Finding out the service endpoint
    endpoint = local("keystone endpoint-get --service {0} | grep {1} | awk '{print $4}'".format(type, url_type), capture=True)
    if not endpoint:
        raise Exception('Could not start monitoring. '
                        'There is not such service type "{0}"'.format(type))

    log.info('Starting monitoring response from {0}'.format(endpoint))

    start_time = time.time()
    while start_time + args['duration'] > time.time():
        try:
            # Trying to get response from service
            requests.get(endpoint)
            res = 1
        except requests.exceptions.ConnectionError:
            res = 0

        log.info('Service {0}, endpoint {1}. Status {2}'.format(type, endpoint, res))

        time.sleep(args['period'])

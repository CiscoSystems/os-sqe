def start(lab, log, args):
    import requests

    service = args['service']      # service type: compute, network, image etc.
    url = args.get('url_type', 'publicURL')     # adminURL / publicURL / internalURL

    # Finding out the service endpoint
    endpoint = lab.cloud.get_service_end_point(service, url)

    try:
        # Trying to get response from service
        requests.get(endpoint)
        res = 1
    except requests.exceptions.ConnectionError:
        res = 0

    log.info('service={0}, endpoint={1}, status={2}'.format(service, endpoint, res))

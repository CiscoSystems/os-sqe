def start(lab, log, args):
    import time
    import requests

    duration = args['duration']
    period = args['period']
    service = args['service']      # service type: compute, network, image etc.
    url = args.get('url_type', 'publicURL')     # adminURL / publicURL / internalURL

    # Finding out the service endpoint
    endpoint = lab.cloud.get_service_end_point(service, url)

    start_time = time.time()
    while start_time + duration > time.time():
        try:
            # Trying to get response from service
            requests.get(endpoint)
            res = 1
        except requests.exceptions.ConnectionError:
            res = 0

        log.info('Service {0}, endpoint {1}. Status {2}'.format(service, endpoint, res))

        time.sleep(period)

if __name__ == '__main__':
    from lab.laboratory import Laboratory
    from lab.logger import create_logger
    from lab.cloud import Cloud

    cloud = Cloud(cloud='g10', user='admin', admin='admin', tenant='admin', password='w32utrzAEaJJHZZqpr6VRPKaZ', end_point='http://10.23.230.132:5000/v2.0/')
    lab = Laboratory('g10.yaml')
    lab.cloud = cloud
    start(lab=lab, log=create_logger('name'), args={'service': 'network', 'duration': 20, 'period': 2})

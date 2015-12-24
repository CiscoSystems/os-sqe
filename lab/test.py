if __name__ == '__main__':
    from lab.laboratory import Laboratory
    from lab.logger import create_logger
    from lab.cloud import Cloud
    from lab.monitors import service_endpoint as tst

    cloud = Cloud(cloud='g10', user='admin', admin='admin', tenant='admin', password='w32utrzAEaJJHZZqpr6VRPKaZ', end_point='http://10.23.230.132:5000/v2.0/')
    lab = Laboratory('g10.yaml')
    lab.cloud = cloud
    tst.start(lab=lab, log=create_logger('name'), args={'service': 'network', 'duration': 20, 'period': 2})

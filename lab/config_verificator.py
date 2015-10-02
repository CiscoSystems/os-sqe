def verify_config(sample_config, config, exception, current_key=None):
    """Verify that config corresponds to sample_config"""
    import validators

    if isinstance(sample_config, list):
        if not len(config):
            exception.message = 'empty list'
            raise exception
        for element in config:
            verify_config(sample_config=sample_config[0], config=element, exception=exception, current_key=current_key)
    elif isinstance(sample_config, dict):
        for sample_key, sample_value in sample_config.iteritems():
            if sample_key not in config:
                exception.message = 'Key "{0}" not in config'.format(sample_key)
                raise exception
            if config[sample_key] is None:
                exception.message = 'Value of "{0}" is empty'.format(sample_key)
                raise exception
            verify_config(sample_config=sample_value, config=config[sample_key], exception=exception, current_key=sample_key)
    else:
        # from this point config and sample_config start to be simple values
        if type(sample_config) is basestring:
            if sample_config.startswith('http') and validators.url(config) is not True:
                exception.message = 'Key "{0}" do not contain valid url: {1}'.format(current_key, config)
                raise exception
            elif sample_config.startswith('email') and not validators.email(config):
                exception.message = 'Key "{0}" do not contain valid email: {1}'.format(current_key, config)
                raise exception
            elif sample_config.startswith('ipv4') and not validators.ipv4(config):
                exception.message = 'Key "{0}" do not contain valid IPv4: {1}'.format(current_key, config)
                raise exception
            elif sample_config.startswith('int'):
                try:
                    int(config)
                except ValueError:
                    exception.message = 'Key "{0}" do not contain valid int number: {1}'.format(current_key, config)
                    raise exception
        elif type(sample_config) is bool and type(config) is not bool:
            exception.message = 'Key "{0}" must be bool: {1}'.format(current_key, config)
            raise exception

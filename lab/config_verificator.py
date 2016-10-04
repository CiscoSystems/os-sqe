def verify_config(sample_config, config, current_key=None):
    """Verify that config corresponds to sample_config"""
    import validators

    def raise_exception(message):
        raise ValueError(message)

    if isinstance(sample_config, list):
        if not len(config):
            raise_exception('empty_list')
        for element in config:
            verify_config(sample_config=sample_config[0], config=element, current_key=current_key)
    elif isinstance(sample_config, dict):
        for sample_key, sample_value in sample_config.items():
            if sample_key not in config:
                raise_exception('Key "{}" not in config'.format(sample_key))
            if config[sample_key] is None:
                raise_exception('Value of "{}" is empty'.format(sample_key))
            verify_config(sample_config=sample_value, config=config[sample_key], current_key=sample_key)
    else:
        # from this point config and sample_config start to be simple values
        if type(sample_config) is str:
            if sample_config.startswith('http') and validators.url(config) is not True:
                raise_exception('Key "{}" do not contain valid url: {}'.format(current_key, config))
            elif sample_config.startswith('email') and not validators.email(config):
                raise_exception('Key "{}" do not contain valid email: {}'.format(current_key, config))
            elif sample_config.startswith('ipv4') and not validators.ipv4(config):
                raise_exception('Key "{}" do not contain valid IPv4: {}'.format(current_key, config))
            elif sample_config.startswith('int'):
                try:
                    int(config)
                except ValueError:
                    raise_exception('Key "{}" do not contain valid int number: {}'.format(current_key, config))
        elif type(sample_config) is bool and type(config) is not bool:
            raise_exception('Key "{}" must be bool: {}'.format(current_key, config))

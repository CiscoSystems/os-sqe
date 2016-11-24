class WithStatusMixIn(object):
    def __repr__(self):
        attributes = vars(self)
        return '\n'.join(['{0}:\t{1}'.format(key, attributes[key]) for key in sorted(attributes.keys()) if not key.startswith('_')])

    def status(self):
        from logger import lab_logger
        lab_logger.debug('\n\nstatus of {0}:\n{1}'.format(type(self), self))

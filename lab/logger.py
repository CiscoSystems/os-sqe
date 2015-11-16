import logging

lab_logger = logging.getLogger('LAB-LOG')
lab_logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s\n\n')

fh = logging.FileHandler('LAB-LOG.txt')
fh.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

ch.setFormatter(formatter)
fh.setFormatter(formatter)

lab_logger.addHandler(ch)
lab_logger.addHandler(fh)

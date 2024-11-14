import logging

custom_fmt='%(asctime)s [%(name)s %(levelname)s]: %(message)s'
custom_datefmt='%H:%M:%S'
custom_formatter = logging.Formatter(fmt=custom_fmt, datefmt=custom_datefmt)
logging.basicConfig(format=custom_fmt, datefmt=custom_datefmt, force=True)
base_logger = logging.getLogger('visualizer')
base_logger.setLevel(logging.DEBUG)


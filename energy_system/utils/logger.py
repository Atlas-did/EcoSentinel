import logging
import sys

def setup_logger(name="EnergySystem"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Standard output handler (for terminal)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    if not logger.handlers:
        logger.addHandler(handler)
        
    return logger

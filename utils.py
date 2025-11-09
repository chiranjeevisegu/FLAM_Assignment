import time

def current_time():
    """Return current readable time."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

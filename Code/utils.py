import random
from collections import deque
import os

# latency buffer (per latency value)
_latency_buffers = {}

def ensure_dir(d):
    if not os.path.exists(d):
        os.makedirs(d)

def apply_latency(bio, latency):
    """
    Simulate sensing latency by buffering biosignals.
    latency: seconds (e.g., 0.5, 1.0)
    """
    if latency <= 0.0:
        return bio

    # assume 20 Hz update rate
    buf_len = max(1, int(latency * 20))

    if latency not in _latency_buffers:
        _latency_buffers[latency] = deque(maxlen=buf_len)

    _latency_buffers[latency].append(bio)

    # return the oldest buffered value
    return _latency_buffers[latency][0]

def apply_missing(bio, rate):
    """
    Simulate missing biosignal samples.
    rate: probability of missing (0.0 ~ 1.0)
    """
    if rate <= 0.0:
        return bio

    if random.random() < rate:
        # hold-last-value behavior
        return bio

    return bio

def apply_noise(bio, std):
    """
    Add Gaussian noise to biosignals.
    """
    if std <= 0.0:
        return bio

    return {
        k: v + random.gauss(0, std)
        for k, v in bio.items()
    }

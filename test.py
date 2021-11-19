from datetime import datetime
from pathlib import Path
import subprocess
import threading
import time
from typing import NamedTuple
import RPi.GPIO as GPIO
import queue
import logging


DUSTPIN_INPUT = 2
DUSTPIN_PARTICLES_DETECTED = 0
SAMPLE_DURATION = 300  # seconds
DATA_FILEPATH = Path("data.csv")
DATA_COMMIT_AND_PUSH_INTERVAL = 10 * 60  # seconds

GPIO.setmode(GPIO.BCM)  # Use Broadcom chip numbering scheme.
GPIO.setup(DUSTPIN_INPUT, GPIO.IN)
while True:
    sample = GPIO.input(DUSTPIN_INPUT)
    print(sample)


"""Record the concentration of air particles over time.
Saves data to a file with this format...
timestamp,particlesDetectedDuration,sampleDuration,concentration
11000,15,30,129
11030,5,30,100
Descriptions of columns:
  - time: Unix (epoch) timestamps. This corresponds to the START of the sample.
  - particlesDetectedDuration: duration during sampleDuration that particles were detected.
  - sampleDuration: duration of this sample.
  - concentration: output of highly complex algorithm that transforms the durations to
      a concentration.
"""

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


GPIO.setmode(GPIO.BCM)  # Use Broadcom chip numbering scheme.
GPIO.setup(DUSTPIN_INPUT, GPIO.IN)
while True:
    print(GPIO.input(DUSTPIN_INPUT))

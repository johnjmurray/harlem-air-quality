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

DUSTPIN_INPUT = 2
DUSTPIN_PARTICLES_DETECTED = 0
SAMPLE_DURATION = 30  # seconds
DATA_FILEPATH = Path("data.csv")
DATA_COMMIT_AND_PUSH_INTERVAL = 10 * 60  # seconds


class Sample(NamedTuple):
    """This object represents one sample of data.

    Properties
    ----------
    particlesDetectedDuration : float
        Duration (s) during sampleDuration that particles were detected.
    sampleDuration : float
        Duration (s) of this sample.
    sampleStart : float
        Unix timestamp of the beginning of this sample.
    """

    particlesDetectedDuration: float
    sampleDuration: float
    sampleStart: float


def getOneSample(duration: float) -> Sample:
    """Detect particles over `duration` seconds.

    Parameters
    ----------
    duration : int, float
        Duration of the sample.

    Returns
    -------
    Instance of `Sample`.
    """
    particlesDetectedDuration = 0
    sampleStart = time.time()
    while (time.time() - sampleStart) < duration:
        pulseStart = time.time()
        pulseStop = pulseStart
        while (
            GPIO.input(DUSTPIN_INPUT) == DUSTPIN_PARTICLES_DETECTED
            and (time.time() - sampleStart) < duration
        ):
            pulseStop = time.time()
        particlesDetectedDuration += pulseStop - pulseStart

    sampleDuration = time.time() - sampleStart
    return Sample(
        sampleDuration=sampleDuration,
        particlesDetectedDuration=particlesDetectedDuration,
        sampleStart=sampleStart,
    )


def getConcentration(x: float) -> float:
    """Get concentration from percentage using equation from test results."""
    return (1.1 * x ** 3) - (3.8 * x ** 2) + (520 * x) + 0.62


def commitAndPushData(period: float) -> None:
    """Commit and push spreadsheet periodically.

    This function is meant to be run in a separate thread to avoid interfering with
    data collection.

    Parameters
    ----------
    period : float
        Time in seconds between subsequent runs.
    """
    # https://stackoverflow.com/a/25251804/5666087
    startTime = time.time()
    while True:
        time.sleep(period - ((time.time() - startTime) % period))
        subprocess.run(["git", "add", str(DATA_FILEPATH)])
        subprocess.run(["git", "commit", "-m", "added rows"])
        subprocess.run(["git", "push"])


def main() -> None:
    GPIO.setmode(GPIO.BCM)  # Use Broadcom chip numbering scheme.
    GPIO.setup(DUSTPIN_INPUT, GPIO.IN)

    # If the file does not exist, create it and write column names.
    if not DATA_FILEPATH.exists():
        DATA_FILEPATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILEPATH.write_text(
            "timestamp,particlesDetectedDuration,sampleDuration,concentration"
        )

    # Run the data uploading pieces in a separate thread.

    dataUploadThread = threading.Thread(
        target=commitAndPushData,
        kwargs={"period": DATA_COMMIT_AND_PUSH_INTERVAL},
        daemon=True,
    )
    dataUploadThread.start()

    while True:
        sample = getOneSample(duration=SAMPLE_DURATION)
        percentage = 100 * sample.particlesDetectedDuration / sample.sampleDuration
        concentration = getConcentration(percentage)

        # Save sample to file.
        row = f"{sample.sampleStart},{sample.particlesDetectedDuration},{sample.sampleDuration},{concentration}"
        with DATA_FILEPATH.open("a") as f:
            f.write(row)

        msg = f"{datetime.now()} | concentration: {concentration:0.2f} pcs/283mL | sample duration: {sample.sampleDuration:0.2f} s"
        print(msg)


if __name__ == "__main__":
    main()

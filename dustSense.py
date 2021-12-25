
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
import pandas
from bokeh.plotting import figure
from bokeh.io import output_file, save, curdoc
from bokeh.models import HoverTool, DatetimeTickFormatter, BasicTickFormatter

DUSTPIN_INPUT = 2
DUSTPIN_PARTICLES_DETECTED = 0
SAMPLE_DURATION = 300  # seconds
DATA_FILEPATH = Path("data.csv")
DATA_COMMIT_AND_PUSH_INTERVAL =  3600 # seconds

logging.basicConfig(level=logging.DEBUG,format='(%(threadName)-9s) %(message)s',)

BUF_SIZE = 0 # infinite queue size
q = queue.Queue(BUF_SIZE)

class ProducerThread(threading.Thread):
    def run(self):
        GPIO.setmode(GPIO.BCM)  # Use Broadcom chip numbering scheme.
        GPIO.setup(DUSTPIN_INPUT, GPIO.IN)
        while True:
            sample = (time.time(), GPIO.input(DUSTPIN_INPUT))
            q.put(sample)

class ConsumerThread(threading.Thread):
    def run(self):
      startOfEpoch = True
      epochDuration = 0

      while True:
          timestamp, value = q.get()

          if startOfEpoch:
              t0 = timestamp
              startOfEpoch = False
              pulseDuration = 0

          if value == DUSTPIN_PARTICLES_DETECTED :
              pulseStart = timestamp
              isLow = True
              while isLow:
                  pulseStop, value = q.get()
                  if value != DUSTPIN_PARTICLES_DETECTED :
                      isLow = False
              pulseDuration += pulseStop - pulseStart

          epochDuration = timestamp - t0

          if epochDuration > SAMPLE_DURATION:
              startOfEpoch = True
              pulseRatio = pulseDuration/epochDuration
              concentration = int(getConcentration(pulseRatio))
              # Save sample to file.
              row = f"{t0:0.3f},{pulseDuration:0.3f},{epochDuration:0.3f},{concentration:d}\n"
              with DATA_FILEPATH.open("a") as f:
                f.write(row)

def updatePlot():
    df = pandas.read_csv("data.csv")
    x = [datetime.fromtimestamp(ts) for ts in df["timestamp"]]
    y = df["concentration"]
    output_file("index.html")
    fig1 = figure(toolbar_location='above',x_axis_type='datetime', title="Concentration of airborne particulate at Saint Nicholas Park, NYC")
    fig1.title.text_font_size = '24pt'
    fig1.yaxis.axis_label =r"$$ Particle \  (>1 \  \mu  m) \   counts/ ft^{3}$$"
    fig1.yaxis.axis_label_text_font_size = '12pt'
    fig1.yaxis.major_label_text_font_size = '10pt'
    fig1.xaxis.axis_label_text_font_size = '12pt'
    fig1.xaxis.major_label_text_font_size = '10pt'
    fig1.background_fill_color = 'beige'
    fig1.xaxis.formatter=DatetimeTickFormatter(days="%m/%d",hours="%H:%M",minutes="%H:%M")
    fig1.yaxis.BasicTickFormatter(precision=1)
    fig1.background_fill_alpha = 0.5
    cr = fig1.circle(x,y,size=3,fill_color='black',hover_fill_color="firebrick",line_color='black',hover_line_color=None)
    fig1.add_tools(HoverTool(tooltips=None, renderers=[cr], mode='hline'))
    fig1.sizing_mode = 'stretch_both'
    curdoc().add_root(fig1)
    curdoc().title = "Harlem Air Quality"
    save(fig1)

def getConcentration(x: float) -> float:
    """Get concentration from ratio using equation from test results. 
    Converted to particles/ft^3
    Manufacturer plot traced and degree 3 polynomial fit applied to estimate relationship
    """
    return 100*(1004388 * x ** 3 - 28273 * x ** 2 + 51483 * x - 5.46)


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
        subprocess.run(["git", "pull"])
        subprocess.run(["git", "add", str(DATA_FILEPATH)])
        subprocess.run(["git", "commit", "-m", "added rows"])
        subprocess.run(["git", "push"])
        updatePlot()


def main() -> None:

    # If the file does not exist, create it and write column names.
    if not DATA_FILEPATH.exists():
        DATA_FILEPATH.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILEPATH.write_text(
            "timestamp,particlesDetectedDuration,sampleDuration,concentration\n"
        )

    p = ProducerThread(name='producer')
    c = ConsumerThread(name='consumer')

    p.start()
    time.sleep(2)
    c.start()
    time.sleep(2)

    # Run the data uploading pieces in a separate thread.
    dataUploadThread = threading.Thread(
        target=commitAndPushData,
        kwargs={"period": DATA_COMMIT_AND_PUSH_INTERVAL},
        daemon=True,
    )
    dataUploadThread.start()


if __name__ == "__main__":
    main()

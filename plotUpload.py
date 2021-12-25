import time
from datetime import datetime
import subprocess
from pathlib import Path
import pandas
from bokeh.plotting import figure
from bokeh.io import output_file, save, curdoc
from bokeh.models import HoverTool, DatetimeTickFormatter, BasicTickFormatter


DATA_FILEPATH = Path("data.csv")
DATA_UPDATE_INTERVAL = 60

def updatePlot():
    """Read data and generate plot in HTML file via Bokeh"""
    df = pandas.read_csv("data.csv")
    print("read csv")
    x = [datetime.fromtimestamp(ts) for ts in df["timestamp"]]
    y = df["concentration"]
    output_file("index.html")
    fig1 = figure(toolbar_location='left',x_axis_type='datetime', title="Concentration of airborne particulate at St Nicholas Park, NYC")
    fig1.title.text_font_size = '24pt'
    fig1.yaxis.axis_label =r"$$ Particle \  (>1 \  \mu  m) \   counts/ ft^{3}$$"
    fig1.yaxis.axis_label_text_font_size = '18pt'
    fig1.yaxis.major_label_text_font_size = '16pt'
    fig1.xaxis.axis_label_text_font_size = '18pt'
    fig1.xaxis.major_label_text_font_size = '16pt'
    fig1.background_fill_color = 'beige'
    fig1.xaxis.formatter=DatetimeTickFormatter(days="%m/%d",hours="%H:%M",minutes="%H:%M")
    fig1.yaxis.formatter=BasicTickFormatter(precision=1)
    fig1.background_fill_alpha = 0.5
    cr = fig1.circle(x,y,size=3,fill_color='black',hover_fill_color="firebrick",line_color='black',hover_line_color='black')
    fig1.add_tools(HoverTool(tooltips=None, renderers=[cr], mode='hline'))
    fig1.sizing_mode = 'stretch_both'
    curdoc().add_root(fig1)
    curdoc().title = "Harlem Air Quality"
    save(fig1)
    print("plot updated")


def commitAndPushData() -> None:
    """Commit and push spreadsheet periodically."""
    # https://stackoverflow.com/a/25251804/5666087
    subprocess.run(["git", "pull"])
    subprocess.run(["git", "add", str(DATA_FILEPATH)])
    subprocess.run(["git", "commit", "-m", "upload data"])
    subprocess.run(["git", "push"])
    print("data and plot uploaded")


def main() -> None:
    while True:
        updatePlot()
        commitAndPushData()
        time.sleep(DATA_UPDATE_INTERVAL)

if __name__ == "__main__":
    main()

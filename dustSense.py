import RPi.GPIO as GPIO
import time
from datetime import datetime
from matplotlib import pyplot as plt
import numpy as np
import subprocess
GPIO.setmode(GPIO.BCM) # use Broadcom chip numbering scheme

# set digital pin 2 as input
dustPin = 2
GPIO.setup(dustPin, GPIO.IN)

plotUpdateMins = 5 # mins
minSampleWindow = 60 # 60 seconds sample time, minimum
timestampVector = []
datetimeVector = []
concVector = []
entryCounter = 0


# Dust sensor outputs LOW on particle detection
while True:
    sampleLowTime = 0
    sampleStart = time.time()
    sampleEnd = time.time()    
    while sampleEnd - sampleStart < minSampleWindow: # for at least [minSampleWindow]
        pulseStart = time.time()
        pulseStop = pulseStart
        # if pin 2 is HIGH, grab start time when it goes LOW
        # if pin 2 is LOW, start time is defined above, grab stop time when it goes HIGH
        #while GPIO.input(dustPin) == 1:
        #    pulseStart = time.time()
        while GPIO.input(dustPin) == 0:
            pulseStop = time.time()
        pulseLowTime = pulseStop - pulseStart # pulse duration
        sampleLowTime+=pulseLowTime # total of all LOW pulse durations in sample window
        sampleEnd = time.time()
    sampleTime = sampleEnd-sampleStart
    percentage = 100*sampleLowTime/sampleTime # ratio of total LOW time to total sample window
    concentration = 1.1*percentage**3-3.8*percentage**2+520*percentage+0.62 # equation from test results
    print('Sample Time: %0.2f, Concentration: %0.2f pcs/283mL'%(sampleTime,concentration))
    entryCounter += 1
    now = datetime.now()
    dateTime = now.strftime("%m-%d %H:%M")
    timestampVector.append(time.time())
    datetimeVector.append(dateTime)
    concVector.append(concentration)
    print(concVector)
    if entryCounter == plotUpdateMins: # update webpage ~every hour
        entryCounter = 0
        
        # 24 hr plot
        N = 24
        if len(timestampVector) < 60*24:            
            #xLabelVec = np.linspace(timestampVector[0],timestampVector[-1],N)
            fig, ax = plt.subplots()
            #ax.axis([timestampVector[0],timestampVector[-1],0,10000])
            ax.scatter(timestampVector,concVector)
        else:
            xLabelVec = np.linspace(timestampVector[-60*24],timestampVector[-1],N)
            fig, ax = plt.scatter(timestampVector[-60*24:],concVector[-60*24:])
            ax.axis([timestampVector[-60*24],timestampVector[-1],0,10000])
        #ax.set_xticks(range(N))
        #ax.set_xticklabels([time.gmtime(t).tm_hour for t in xLabelVec])
        ax.set_xlabel('Date')
        ax.set_ylabel('Conc. (pcs/283mL)')
        fig.savefig('images/1day.jpg')
        subprocess.run(["git","add","*"])
        subprocess.run(["git","commit","-m","'added image'"])
        subprocess.run(["git","push"])
        
        
        '''
        try:
            plt.scatter(timestampVector[-60*24*7:],concVector[-60*24*7:])
            plt.axis([timestampVector[-60*24*7],timestampVector[-1],0,10000])
        except:
            plt.scatter(timestampVector,concVector)
            plt.axis([timestampVector[0],timestampVector[-1],0,10000])
        plt.xlabel('Date')
        plt.ylabel('Conc. (pcs/283mL)')
        plt.savefig('images/7day.jpg')
        #daily plot minute
        #7 day plot hourly average
        #30 day plot daily average
        #90 day plot daily average
        #365 plot daily average
        '''
        
        

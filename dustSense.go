// Record concentration of dust particles in the air over time.
//
// Compile:
//   GOOS=linux GOARCH=arm GOARM=6 go build -o dust-linux-armv6 .
//
// See here for more info: https://github.com/golang/go/wiki/GoArm

package main

import (
	"flag"
	"fmt"
	"io/ioutil"
	"log"
	"math"
	"os"
	"os/exec"
	"sync"
	"time"

	"github.com/stianeikeland/go-rpio/v4"
)

// TODO: make these things command-line arguments.
const dustPinInput = rpio.Pin(2)
const dustPinParticlesDetected = rpio.Low

var sampleDuration time.Duration
var dataPath string
var dataCommitAndPushInterval time.Duration
var channelBuffer int

func main() {

	flag.StringVar(&dataPath, "data-path", "data-go.csv", "path to CSV in which to save data")
	flag.DurationVar(&sampleDuration, "sample-duration", 5*time.Minute, "duration of one sample")
	flag.DurationVar(&dataCommitAndPushInterval, "push-interval", 10*time.Minute, "time between pushes to GitHub")
	flag.IntVar(&channelBuffer, "buffer-size", 64, "buffer size for each channel (ie queue)")
	flag.Parse()

	if err := rpio.Open(); err != nil {
		log.Fatalf(fmt.Sprint("unable to open gpio", err.Error()))
	}
	defer rpio.Close()
	dustPinInput.Input()

	prepareSpreadsheet()

	ct := make(chan int64, channelBuffer)      // timestamps
	cv := make(chan rpio.State, channelBuffer) // pin values
	defer close(ct)
	defer close(cv)

	var wg sync.WaitGroup
	wg.Add(3)

	go produce(ct, cv, &wg)
	go consume(ct, cv, &wg)
	go repeat(dataCommitAndPushInterval, commitAndPush, &wg)

	// Block until goroutines in WaitGroup are done.
	wg.Wait()
}

// produce pushes timestamps to channel `ct` and pin values to channel `cv`.
func produce(ct chan int64, cv chan rpio.State, wg *sync.WaitGroup) {
	defer wg.Done()
	for {
		cv <- dustPinInput.Read()
		ct <- time.Now().UnixNano()
	}
}

// consume receives timestamps from channel `ct` and pin values from channel `cv`.
// These values are then processed and saved to a spreadsheet.
func consume(ct chan int64, cv chan rpio.State, wg *sync.WaitGroup) {
	defer wg.Done()

	startOfEpoch := true
	var epochDuration, t0 int64
	var pulseDuration, pulseStart, pulseStop int64
	var isLow bool
	var pulseRatio, concentration float64
	var sample Sample

	// https://stackoverflow.com/a/17825968/5666087
	for timestamp := range ct {
		value := <-cv

		if startOfEpoch {
			t0 = timestamp
			startOfEpoch = false
			pulseDuration = 0
		}

		if value == dustPinParticlesDetected {
			pulseStart = timestamp
			isLow = true
			for {
				pulseStop = <-ct

				if value := <-cv; value != 0 {
					isLow = false
				}
				if !isLow {
					break
				}
			}
			pulseDuration += pulseStop - pulseStart
		}

		epochDuration = timestamp - t0

		if epochDuration > sampleDuration.Nanoseconds() {
			startOfEpoch = true
			sample.timestamp = nanoSecondsToSeconds(t0)
			sample.particlesDetectedDuration = nanoSecondsToSeconds(pulseDuration)
			sample.duration = nanoSecondsToSeconds(epochDuration)
			pulseRatio = sample.particlesDetectedDuration / sample.duration
			concentration = getConcentration(pulseRatio)
			sample.concentration = concentration
			sample.appendToSpreadsheet()
		}
	}
}

// commitAndPush uses `git` to commit and push the spreadsheet with data to a remote (eg GitHub).
func commitAndPush() {
	log.Println("committing and pushing data")
	if err := exec.Command("git", "add", dataPath).Run(); err != nil {
		log.Printf("ignoring `git add` failure: %s\n", err)
	}
	if err := exec.Command("git", "commit", "-m", "update data", dataPath).Run(); err != nil {
		log.Printf("ignoring `git commit` failure: %s\n", err)
	}
	if err := exec.Command("git", "push", "origin").Run(); err != nil {
		log.Printf("ignoring `git push` failure: %s\n", err)
	}
}

// repeat repeats function `f` once per `duration` time. This function runs infinitely.
func repeat(duration time.Duration, f func(), wg *sync.WaitGroup) {
	defer wg.Done()
	// https://golang.org/pkg/time/#NewTicker
	ticker := time.NewTicker(duration)
	defer ticker.Stop()

	for _ = range ticker.C {
		f()
	}
}

// prepareSpreadsheet creates the spreadsheet and writes the header if the files does not already exist.
func prepareSpreadsheet() {
	header := []byte("timestamp,particlesDetectedDuration,sampleDuration,concentration\n")
	// https://stackoverflow.com/a/12518877/5666087
	if _, err := os.Stat(dataPath); os.IsNotExist(err) {
		err := ioutil.WriteFile(dataPath, header, 0644)
		if err != nil {
			log.Fatalf("Unable to write file: %v\n", err)
		}
	}
}

// getConcentration calculates concentration from ratio using equation from test results.
func getConcentration(ratio float64) float64 {
	return 1.1*math.Pow(ratio, 3) - 3.8*math.Pow(ratio, 2) + 520*ratio + 0.62
}

// nanoSecondsToSeconds converts nanoseconds to seconds.
func nanoSecondsToSeconds(nano int64) float64 {
	return float64(nano) / math.Pow(10, 9)
}

// Sample represents one sample of data.
type Sample struct {
	// Epoch time in seconds.
	timestamp float64
	// Duration in seconds that particles were detected during this sample.
	particlesDetectedDuration float64
	// Duration of this sample.
	duration float64
	// Concentration calculated for this sample.
	concentration float64
}

// Sample.String() returns the string representation of the Sample in CSV format.
func (s *Sample) String() string {
	return fmt.Sprintf("%.3f,%.3f,%.3f,%.3f\n", s.timestamp, s.particlesDetectedDuration, s.duration, s.concentration)
}

// Sample.appendToSpreadsheet appends one line of data to the spreadsheet.
// Adapted from https://golang.org/pkg/os/#example_OpenFile_append.
func (s *Sample) appendToSpreadsheet() {
	f, err := os.OpenFile(dataPath, os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		log.Fatalf("failed to open spreadsheet: %v\n", err)
	}
	if _, err := f.Write([]byte(s.String())); err != nil {
		_ = f.Close() // ignore error; Write error takes precedence
		log.Fatal(err)
	}
	if err := f.Close(); err != nil {
		log.Fatal(err)
	}
}

// Record concentration of dust particles in the air over time.
//
// Compile:
//   GOARM=6 GOARCH=arm go build -o dust-linux-armv6 .
//
// See here for more info: https://github.com/golang/go/wiki/GoArm

package main

import (
	"fmt"
	"io/ioutil"
	"log"
	"math"
	"math/rand"
	"os"
	"os/exec"
	"sync"
	"time"
)

const dustPinInput = 2
const dustPinParticlesDetected = 0
const sampleDuration = 5 * time.Second
const dataPath = "data-go.csv"
const dataCommitAndPushInterval = 10 * time.Minute
const channelBuffer = 64 // TODO: what should this be?

func main() {

	prepareSpreadsheet()

	ct := make(chan int64, channelBuffer) // timestamps
	cv := make(chan int, channelBuffer)   // pin values
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
func produce(ct chan int64, cv chan int, wg *sync.WaitGroup) {
	ticker := time.NewTicker(time.Millisecond * 100)
	defer ticker.Stop()
	defer wg.Done()
	r := rand.New(rand.NewSource(42))
	for _ = range ticker.C {
		timestamp := time.Now().UnixNano()
		value := r.Intn(2)
		ct <- timestamp
		cv <- value
	}
}

// consume receives timestamps from channel `ct` and pin values from channel `cv`.
// These values are then processed and saved to a spreadsheet.
func consume(ct chan int64, cv chan int, wg *sync.WaitGroup) {
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
			log.Printf("epoch duration: %.3f", sample.duration)
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

// nanoSecondsToSeconds converts nanoseconds to seconds.
func nanoSecondsToSeconds(nano int64) float64 {
	return float64(nano) / math.Pow(10, 9)
}

// Sample.String() returns the string representation of the Sample in CSV format.
func (s *Sample) String() string {
	return fmt.Sprintf("%.3f,%.3f,%.3f,%.3f\n", s.timestamp, s.particlesDetectedDuration, s.duration, s.concentration)
}

// Sample.appendToSpreadsheet appends one line of data to the spreadsheet.
// Adapted from https://golang.org/pkg/os/#example_OpenFile_append.
func (s *Sample) appendToSpreadsheet() {

	fmt.Printf(s.String())

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

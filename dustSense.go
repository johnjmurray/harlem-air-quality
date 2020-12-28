package main

import (
	"fmt"
	"log"
	"math/rand"
	"os/exec"
	"sync"
	"time"
)

const dataPath = "synthetic.csv"

func main() {
	ct := make(chan int64, 64) // timestamps
	cv := make(chan int, 64)   // pin values
	defer close(ct)
	defer close(cv)

	var wg sync.WaitGroup
	wg.Add(3)

	go publish(ct, cv, &wg)
	go subscribe(ct, cv, &wg)
	go repeat(time.Minute*10, commitAndPush, &wg)

	// Block until goroutines in WaitGroup are done.
	wg.Wait()

}

// publish pushes timestamps to channel `ct` and pin values to channel `cv`.
func publish(ct chan int64, cv chan int, wg *sync.WaitGroup) {
	ticker := time.NewTicker(time.Second)
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

// subscribe receives timestamps from channel `ct` and pin values from channel `cv`.
// These values are then processed and saved to a spreadsheet.
func subscribe(ct chan int64, cv chan int, wg *sync.WaitGroup) {
	defer wg.Done()
	// https://stackoverflow.com/a/17825968/5666087
	for timestamp := range ct {
		value := <-cv
		fmt.Printf("received %d %d\n", timestamp, value)
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

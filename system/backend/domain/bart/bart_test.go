package bart_test

import (
	"context"
	"fmt"
	"log"
	"runtime"
	"sync"
	"testing"
	"time"

	"changkun.de/x/human-preference-prior/domain/bart"
)

const txt = "Vice President Dick Cheney will serve as acting president briefly Saturday while President Bush is anesthetized for a routine colonoscopy, White House spokesman Tony Snow said Friday. Bush is scheduled to have the medical procedure, expected to take about 2 1/2 hours, at the presidential retreat at Camp David, Maryland, Snow said. Bush's last colonoscopy was in June 2002, and no abnormalities were found, Snow said. The president's doctor had recommended a repeat procedure in about five years. The procedure will be supervised by Dr. Richard Tubb and conducted by a multidisciplinary team from the National Naval Medical Center in Bethesda, Maryland, Snow said. A colonoscopy is the most sensitive test for colon cancer, rectal cancer and polyps, small clumps of cells that can become cancerous, according to the Mayo Clinic. Small polyps may be removed during the procedure. Snow said that was the case when Bush had colonoscopies before becoming president. Snow himself is undergoing chemotherapy for cancer that began in his colon and spread to his liver. Snow told reporters he had a chemo session scheduled later Friday. Watch Snow talk about Bush's procedure and his own colon cancer » . \"The president wants to encourage everybody to use surveillance,\" Snow said. The American Cancer Society recommends that people without high-risk factors or symptoms begin getting screened for signs of colorectal cancer at age 50."

func TestSummarizer(t *testing.T) {
	conf := &bart.SummarizeSpace{
		ReductionRatio: 0.5,
		TopP:           0.5,
		Temperature:    0.5,
		LengthPenalty:  0.5,
	}

	x, err := bart.Summarizer(context.TODO(), txt, conf)
	if err != nil {
		t.Fatal(err)
	}

	t.Log(x)
}

func BenchmarkSummarizer(b *testing.B) {
	conf := &bart.SummarizeSpace{
		ReductionRatio: 0.5,
		TopP:           0.5,
		Temperature:    0.5,
		LengthPenalty:  0.5,
	}
	b.SetParallelism(runtime.NumCPU())
	b.RunParallel(func(p *testing.PB) {
		for p.Next() {
			_, err := bart.Summarizer(context.TODO(), txt, conf)
			if err != nil {
				b.Fatal(err)
			}
		}
	})
}

func TestPressure(t *testing.T) {
	conf := &bart.SummarizeSpace{
		ReductionRatio: 0.5,
		TopP:           0.5,
		Temperature:    0.5,
		LengthPenalty:  0.5,
	}
	N := 6
	log.Println("N: ", N)
	wg := sync.WaitGroup{}
	wg.Add(N)

	mu := sync.Mutex{}
	waiting := []time.Duration{}
	for i := 0; i < N; i++ {
		go func() {
			defer wg.Done()
			start := time.Now()
			_, err := bart.Summarizer(context.TODO(), txt, conf)
			if err != nil {
				log.Fatal(err)
			}
			mu.Lock()
			waiting = append(waiting, time.Since(start))
			mu.Unlock()
		}()
	}
	wg.Wait()
	sum := 0.0
	for _, t := range waiting {
		sum += float64(t.Milliseconds())
	}
	fmt.Println("Avg Response Time: ", sum/float64(N))
}

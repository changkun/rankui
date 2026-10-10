package main

import (
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
)

func init() {
	log.SetFlags(log.Ldate | log.Ltime | log.Lmicroseconds | log.Llongfile)
}

type Context string

const (
	TextSummarization     Context = "text-summarization"
	ImageColorEnhancement Context = "image-color-enhancement"
	MeshSimplification    Context = "mesh-simplification"
)

type UserInterface int

const (
	Pointwise UserInterface = 1
	Pairwise  UserInterface = 2
	Listwise  UserInterface = 4
)

func TopK(alternatives int) UserInterface {
	return UserInterface(alternatives)
}

type Optimizer string

const (
	Plain       Optimizer = "plain"
	Progressive Optimizer = "bo"
	Pareto      Optimizer = "Pareto"
)

type Assistant string

const (
	None      Assistant = "none"
	Correct   Assistant = "correct"
	Incorrect Assistant = "incorrect"
)

type Control string

type HumanDecision struct {
	Context          Context
	Iteration        int
	UserInterface    UserInterface
	DesignParameters int
	Optimizer        Optimizer
	Assistant        Assistant
	Control          string
}

func main() {
	router := gin.Default()

	// Allow all origin.
	router.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"*"},
		AllowMethods:     []string{"GET", "POST", "PUT", "PATCH"},
		AllowHeaders:     []string{"*"},
		ExposeHeaders:    []string{"Content-Length"},
		AllowCredentials: true,
		AllowOriginFunc:  func(origin string) bool { return true },
		MaxAge:           12 * time.Hour,
	}))

	// the database - file system based
	router.Static("data", "data")

	domains := []taskContext{ctxText, ctxImage, ctxMesh}
	for _, domain := range domains {
		// pointwise interface, 1-RS
		router.StaticFS(fmt.Sprintf("/prefprior/%s/pointwise", domain), http.Dir(fmt.Sprintf("../frontend/pointwise-%s/build", domain)))
		router.POST(fmt.Sprintf("/prefprior/%s/pointwise/begin", domain), optmizationBegin(domain, interfacePointwise))
		router.POST(fmt.Sprintf("/prefprior/%s/pointwise/iterate", domain), optimizationIterate(domain, interfacePointwise))
		router.POST(fmt.Sprintf("/prefprior/%s/pointwise/finish", domain), optimizationFinish(domain, interfacePointwise))

		// pairwise interface, 2-ANFC
		router.StaticFS(fmt.Sprintf("/prefprior/%s/pairwise", domain), http.Dir(fmt.Sprintf("../frontend/pairwise-%s/build", domain)))
		router.POST(fmt.Sprintf("/prefprior/%s/pairwise/begin", domain), optmizationBegin(domain, interfacePairwise))
		router.POST(fmt.Sprintf("/prefprior/%s/pairwise/iterate", domain), optimizationIterate(domain, interfacePairwise))
		router.POST(fmt.Sprintf("/prefprior/%s/pairwise/finish", domain), optimizationFinish(domain, interfacePairwise))

		// listwise ranking interface, n-RS
		router.StaticFS(fmt.Sprintf("/prefprior/%s/listwise/rating", domain), http.Dir(fmt.Sprintf("../frontend/listwise-rating-%s/build", domain)))
		router.POST(fmt.Sprintf("/prefprior/%s/listwise/rating/begin", domain), optmizationBegin(domain, interfaceListwiseRating))
		router.POST(fmt.Sprintf("/prefprior/%s/listwise/rating/iterate", domain), optimizationIterate(domain, interfaceListwiseRating))
		router.POST(fmt.Sprintf("/prefprior/%s/listwise/rating/finish", domain), optimizationFinish(domain, interfaceListwiseRating))

		// listwise ranking interface, n-AFC
		router.StaticFS(fmt.Sprintf("/prefprior/%s/listwise/notie", domain), http.Dir(fmt.Sprintf("../frontend/listwise-notie-%s/build", domain)))
		router.POST(fmt.Sprintf("/prefprior/%s/listwise/notie/begin", domain), optmizationBegin(domain, interfaceListwiseNoTie))
		router.POST(fmt.Sprintf("/prefprior/%s/listwise/notie/iterate", domain), optimizationIterate(domain, interfaceListwiseNoTie))
		router.POST(fmt.Sprintf("/prefprior/%s/listwise/notie/finish", domain), optimizationFinish(domain, interfaceListwiseNoTie))

		// listwise ranking interface, n-ANFC
		router.StaticFS(fmt.Sprintf("/prefprior/%s/listwise/cantie", domain), http.Dir(fmt.Sprintf("../frontend/listwise-cantie-%s/build", domain)))
		router.POST(fmt.Sprintf("/prefprior/%s/listwise/cantie/begin", domain), optmizationBegin(domain, interfaceListwiseCantie))
		router.POST(fmt.Sprintf("/prefprior/%s/listwise/cantie/iterate", domain), optimizationIterate(domain, interfaceListwiseCantie))
		router.POST(fmt.Sprintf("/prefprior/%s/listwise/cantie/finish", domain), optimizationFinish(domain, interfaceListwiseCantie))

		// listwise ranking interface, n-ANFCD
		router.StaticFS(fmt.Sprintf("/prefprior/%s/listwise/ranking", domain), http.Dir(fmt.Sprintf("../frontend/listwise-ranking-%s/build", domain)))
		router.POST(fmt.Sprintf("/prefprior/%s/listwise/ranking/begin", domain), optmizationBegin(domain, interfaceListwiseRanking))
		router.POST(fmt.Sprintf("/prefprior/%s/listwise/ranking/iterate", domain), optimizationIterate(domain, interfaceListwiseRanking))
		router.POST(fmt.Sprintf("/prefprior/%s/listwise/ranking/finish", domain), optimizationFinish(domain, interfaceListwiseRanking))
	}

	router.Run(":8088")
}

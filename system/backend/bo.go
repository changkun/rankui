package main

import (
	"changkun.de/x/human-preference-prior/optimizers"
)

// Note: must synched with front end UI.
const (
	maxIteration  = 20
	initialSample = 4 // This is smaller than frontend UI, because we started to run optimizer in the 5th iteration.
)

func bayesianOptimization(ctx taskContext, method userInterface, nparams int, input *iterateInput) [][]float64 {
	if input.CurrentIteration < initialSample {
		switch method {
		case interfacePointwise:
			return optimizers.SobolPointSampling(string(method), nparams, initialSample)[input.CurrentIteration]
			// return optimizers.PointwiseSamples[nparams][input.CurrentIteration]
		case interfacePairwise:
			return optimizers.SobolPointSampling(string(method), nparams, initialSample)[input.CurrentIteration]
			// return optimizers.PairwiseSamples[nparams][input.CurrentIteration]
		case interfaceListwiseNoTie, interfaceListwiseCantie, interfaceListwiseRating, interfaceListwiseRanking:
			return optimizers.SobolPointSampling(string(method), nparams, initialSample)[input.CurrentIteration]
			// return optimizers.ListwiseSamples[nparams][input.CurrentIteration]
		}
	}

	switch method {
	case interfacePointwise:
		return [][]float64{optimizers.PointwiseBO(string(ctx), input.UserID, input.SessionID, input.TaskID, nparams)}
	case interfacePairwise:
		return optimizers.PairwiseBO(string(ctx), input.UserID, input.SessionID, input.TaskID, nparams)
	case interfaceListwiseRating:
		return optimizers.ListwiseBOrating(string(ctx), input.UserID, input.SessionID, input.TaskID, nparams)
	case interfaceListwiseNoTie:
		return optimizers.ListwiseBOnotie(string(ctx), input.UserID, input.SessionID, input.TaskID, nparams)
	case interfaceListwiseCantie:
		return optimizers.ListwiseBOcantie(string(ctx), input.UserID, input.SessionID, input.TaskID, nparams)
	case interfaceListwiseRanking:
		return optimizers.ListwiseBOranking(string(ctx), input.UserID, input.SessionID, input.TaskID, nparams)
	}

	return nil
}

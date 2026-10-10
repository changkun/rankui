import torch
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from botorch.models import SingleTaskGP
from botorch.models.pairwise_gp import PairwiseGP, PairwiseLaplaceMarginalLogLikelihood
from botorch.acquisition import UpperConfidenceBound
from botorch.acquisition.preference import AnalyticExpectedUtilityOfBestOption
from botorch.acquisition.monte_carlo import qExpectedImprovement, qNoisyExpectedImprovement
from botorch.fit import fit_gpytorch_model
from botorch.optim import optimize_acqf
from botorch.utils import draw_sobol_samples
from gpytorch.mlls import ExactMarginalLogLikelihood
from gpytorch.kernels.matern_kernel import MaternKernel
from gpytorch.kernels.scale_kernel import ScaleKernel
from gpytorch.priors.torch_priors import GammaPrior
from itertools import combinations

import warnings
warnings.filterwarnings("ignore")


def utility_bo(X: torch.tensor, y: torch.tensor, dim: int, q: int = 1, mode: str = 'human'):
    """Utility-based Bayesian Optimization: this function fits the input data to a
    GP model and returns the optimal hyperparameters for the next iteration of evaluation.

    This function can be used when the input interface is a single value slider.
    If the input interface contains multiple candidates and multiple corresponding sliders,
    set q > 1 to generate multiple candidates for the next evaluation.
    Args:
        X (torch.tensor): n x dim matrix of input points.
        y (torch.tensor): n x 1 vector of utility values.
        dim (int): number of hyperparameters.
        q (int, optional): number of candidates to be generated. Defaults to 1.
        mode (str, optional): 'human' or 'simulate'. Defaults to 'human'.
    Returns:
        torch.tensor: q x dim matrix of optimal hyperparameters.
        torch.tensor: q x 1 vector of acquisition values.
    """
    gp = SingleTaskGP(X, y)
    mll = ExactMarginalLogLikelihood(gp.likelihood, gp)
    fit_gpytorch_model(mll)

    # For use cases with human interactions, we use qNoisyExpectedImprovement
    # to avoid the over exploitation and deal with noisy inputs. In simulation,
    # we use UCB to avoid the over exploration and validate the exploitation
    # performance.
    if mode == 'human':
        acqf = qNoisyExpectedImprovement(gp, X)
    elif mode == 'simulate':
        acqf = UpperConfidenceBound(gp, beta=0.1)
    else:
        raise ValueError('Invalid mode: {}'.format(mode))
    candidates, acq_val = optimize_acqf(
        acqf,
        bounds=torch.stack([torch.zeros(dim), torch.ones(dim)]),
        q=q,
        num_restarts=5,
        raw_samples=20,
    )
    return candidates, acq_val


def pairwise_bo(X: torch.tensor, y: torch.tensor, dim: int):
    """Pairwise Bayesian Optimization: this function fits the input data to a
    GP model and returns the optimal hyperparameters for the next iteration of
    evaluation. This function can only be used for paired user interface.

    Args:
        X (torch.tensor): n x dim matrix of input points.
        y (torch.tensor): n x 2 vector of preferential pairs. The first column
            is the index of the preferred candidate, the second column is the
            index of the less preferred candidate compared to the first candidate.
        dim (int): number of hyperparameters.
    Returns:
        torch.tensor: q x dim matrix of optimal hyperparameters.
        torch.tensor: q x 1 vector of acquisition values.
    """
    while True:
        try:
            bounds = torch.stack([torch.zeros(dim), torch.ones(dim)])
            gp = PairwiseGP(X, y, covar_module=ScaleKernel(
                MaternKernel(nu=2.5, lengthscale_prior=GammaPrior(3.0, 6.0)),
                outputscale_prior=GammaPrior(2.0, 0.15),
            ))
            mll = PairwiseLaplaceMarginalLogLikelihood(gp.likelihood, gp)
            fit_gpytorch_model(mll)

            candidates, acq_val = optimize_acqf(
                acq_function=AnalyticExpectedUtilityOfBestOption(
                    pref_model=gp),
                bounds=bounds,
                q=2,
                num_restarts=5,
                raw_samples=20,
            )
            break
        except:
            continue
    return candidates, acq_val


def mixed_bo(X: torch.tensor, y: torch.tensor, dim: int, q: int = 2, mode='human'):
    """Listwise Bayesian Optimization: this function fits the input data to a
    GP model and returns the optimal hyperparameters for the next iteration of
    evaluation. This function can be used for ranking user interface.

    This model mixes a PairseGP and a SingleTaskGP model for learning the ranking.
    The provided X, and y are the data for pairwise training. When the training
    completes, we will use the trained utility to train another SingleTaskGP model.
    The acquisition function is a noisy EI function.

    Args:
        X (torch.tensor): n x dim matrix of input points.
        y (torch.tensor): n x 2 vector of preferential pairs. The first column
            is the index of the preferred candidate, the second column is the
            index of the less preferred candidate compared to the first candidate.
        dim (int): number of hyperparameters.
        q (int, optional): number of candidates to be generated. Defaults to 2.
        mode (str, optional): 'human' or 'simulate'. Defaults to 'human'.

    Returns:
        torch.tensor: q x dim matrix of optimal hyperparameters.
        torch.tensor: q x 1 vector of acquisition values.
    """
    # Infer ranking utility from data.
    rankGP = PairwiseGP(X, y, covar_module=ScaleKernel(
                        MaternKernel(
                            nu=2.5, lengthscale_prior=GammaPrior(3.0, 6.0)),
                        outputscale_prior=GammaPrior(2.0, 0.15)))
    mll = PairwiseLaplaceMarginalLogLikelihood(rankGP.likelihood, rankGP)
    fit_gpytorch_model(mll)
    if rankGP.utility is not None:
        y_utility = rankGP.utility.detach().clone().requires_grad_(True).reshape(-1, 1)
    else:
        # Retry another trianing and see if the utility will converge.
        maxRetry = 10
        for i in range(maxRetry):
            rankGP = PairwiseGP(X, y, covar_module=ScaleKernel(
                MaternKernel(nu=2.5, lengthscale_prior=GammaPrior(3.0, 6.0)),
                outputscale_prior=GammaPrior(2.0, 0.15),
            ))
            mll = PairwiseLaplaceMarginalLogLikelihood(
                rankGP.likelihood, rankGP)
            fit_gpytorch_model(mll)
            if rankGP.utility is not None:
                y_utility = rankGP.utility.detach().clone().requires_grad_(True).reshape(-1, 1)
                break
        # If the utility does not converge, we will randomly remove the y and do more training
        if rankGP.utility is None:
            # Randomly remove half of the ranks.
            y_sample = y[torch.randperm(y.size(0))[:y.size(0)//2]]
            rankGP = PairwiseGP(X, y_sample, covar_module=ScaleKernel(
                MaternKernel(nu=2.5, lengthscale_prior=GammaPrior(3.0, 6.0)),
                outputscale_prior=GammaPrior(2.0, 0.15),
            ))
            mll = PairwiseLaplaceMarginalLogLikelihood(
                rankGP.likelihood, rankGP)
            fit_gpytorch_model(mll)
            if rankGP.utility is not None:
                y_utility = rankGP.utility.detach().clone().requires_grad_(True).reshape(-1, 1)
            else:
                # We have done our best effort. Let's just set the utility to be zero.
                y_utility = torch.tensor(
                    [[0.0] * y.size(0)], dtype=torch.float32)

    # Train model with ranking utility.
    bounds = torch.stack([torch.zeros(dim), torch.ones(dim)])
    utilityGP = SingleTaskGP(X, y_utility)
    fit_gpytorch_model(ExactMarginalLogLikelihood(
        utilityGP.likelihood, utilityGP))

    # For use cases with human interactions, we use qNoisyExpectedImprovement
    # to avoid the over exploitation and deal with noisy inputs. In simulation,
    # we use UCB to avoid the over exploration and validate the exploitation
    # performance.
    if mode == 'human':
        acqf = qNoisyExpectedImprovement(utilityGP, X)
    elif mode == 'simulate':
        acqf = UpperConfidenceBound(utilityGP, beta=0.1)
    else:
        raise ValueError('Invalid mode: {}'.format(mode))
    candidates, acq_val = optimize_acqf(
        acqf,
        bounds=bounds,
        q=1,
        num_restarts=5,
        raw_samples=20,
    )
    return candidates, acq_val  # this is not a paired candidates


def generate_random_samples(utility, n, dim=2):
    """ Generate X and y with size n"""
    # X is randomly sampled from dim-dimentional unit cube
    # we recommend using double as opposed to float tensor here for
    # better numerical stability
    X = torch.rand(n, dim, dtype=torch.float32)
    y = utility(X)
    return X, y


def generate_sobol_samples(utility, n, dim=2):
    """ Generate X and y with size n"""
    bounds = torch.stack([torch.zeros(dim), torch.ones(dim)])
    X = draw_sobol_samples(bounds, 1, n)[0]
    y = utility(X)
    return X, y


def generate_comparisons(y, n_comp=0, noise=0, replace=False):
    """  Create pairwise comparisons with noise """
    # generate all possible pairs of elements in y
    all_pairs = np.array(list(combinations(range(y.shape[0]), 2)))
    comp_pairs = all_pairs
    if n_comp != 0:
        # randomly select n_comp pairs from all_pairs
        comp_pairs = all_pairs[np.random.choice(
            range(len(all_pairs)), n_comp, replace=replace)]

    # add gaussian noise to the latent y values
    c0 = y.to('cpu')[comp_pairs[:, 0]] + \
        np.random.standard_normal(len(comp_pairs)) * noise
    c1 = y.to('cpu')[comp_pairs[:, 1]] + \
        np.random.standard_normal(len(comp_pairs)) * noise
    reverse_comp = (c0 < c1).numpy()
    comp_pairs[reverse_comp, :] = np.flip(comp_pairs[reverse_comp, :], 1)
    comp_pairs = torch.tensor(comp_pairs).long()
    return comp_pairs

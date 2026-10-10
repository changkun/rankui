import os
import time
import math
import logging
from functools import partial
from abc import ABCMeta, abstractmethod
from timeit import default_timer as now
from typing import Tuple, Dict, List, Callable, Optional

import numpy as np
import scipy as sp
import pandas as pd
import numpy.linalg as la
from scipy.linalg import inv, svd
from scipy.stats import norm

import GPy
from GPy.util.linalg import pdinv, jitchol, dpotrs, dtrtrs, symmetrify, tdot
from GPy.inference.latent_function_inference.expectation_propagation import posteriorParams
from GPy.inference.latent_function_inference.posterior import PosteriorEP
from emukit.core import ContinuousParameter, ParameterSpace
from emukit.core.interfaces import IModel
from emukit.core.acquisition import Acquisition
from emukit.core.optimization import ContextManager, GradientAcquisitionOptimizer
from emukit.bayesian_optimization.loops import BayesianOptimizationLoop


def random_sample(bounds: np.ndarray, k: int) -> np.ndarray:
    """
    Generate a set of k n-dimensional points sampled uniformly at random
    :param bounds: n x 2 dimenional array containing upper/lower bounds for each dimension
    :param k: number of samples
    :return: k x n array containing the sampled points
    """

    # k: Number of points
    n = len(bounds)  # Dimensionality of each point
    X = np.zeros((k, n))
    for i in range(n):
        X[:, i] = np.random.uniform(bounds[i][0], bounds[i][1], k)

    return X


def grid_sample(n: int) -> np.ndarray:
    """
    Get a grid with equally distanced points

    :param n: dimensionality of the data
    :return: 2^n samples that are placed in a n dimendional grid
    """
    if n == 1:
        ret = np.array([[0], [1]])
    if n == 2:
        ret = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
    if n == 3:
        ret = np.array([[0, 0, 0], [0, 0, 1], [0, 1, 0], [0, 1, 1], [
                       1, 0, 0], [1, 0, 1], [1, 1, 0], [1, 1, 1]])
    if n == 4:
        ret = np.array(
            [
                [0, 0, 0, 0],
                [0, 0, 0, 1],
                [0, 0, 1, 0],
                [0, 0, 1, 1],
                [0, 1, 0, 0],
                [0, 1, 0, 1],
                [0, 1, 1, 0],
                [0, 1, 1, 1],
                [1, 0, 0, 0],
                [1, 0, 0, 1],
                [1, 0, 1, 0],
                [1, 0, 1, 1],
                [1, 1, 0, 0],
                [1, 1, 0, 1],
                [1, 1, 1, 0],
                [1, 1, 1, 1],
            ]
        )
    if n == 5:
        ret = np.array(
            [
                [0, 0, 0, 0, 0],
                [0, 0, 0, 0, 1],
                [0, 0, 0, 1, 0],
                [0, 0, 0, 1, 1],
                [0, 0, 1, 0, 0],
                [0, 0, 1, 0, 1],
                [0, 0, 1, 1, 0],
                [0, 0, 1, 1, 1],
                [0, 1, 0, 0, 0],
                [0, 1, 0, 0, 1],
                [0, 1, 0, 1, 0],
                [0, 1, 0, 1, 1],
                [0, 1, 1, 0, 0],
                [0, 1, 1, 0, 1],
                [0, 1, 1, 1, 0],
                [0, 1, 1, 1, 1],
                [1, 0, 0, 0, 0],
                [1, 0, 0, 0, 1],
                [1, 0, 0, 1, 0],
                [1, 0, 0, 1, 1],
                [1, 0, 1, 0, 0],
                [1, 0, 1, 0, 1],
                [1, 0, 1, 1, 0],
                [1, 0, 1, 1, 1],
                [1, 1, 0, 0, 0],
                [1, 1, 0, 0, 1],
                [1, 1, 0, 1, 0],
                [1, 1, 0, 1, 1],
                [1, 1, 1, 0, 0],
                [1, 1, 1, 0, 1],
                [1, 1, 1, 1, 0],
                [1, 1, 1, 1, 1],
            ]
        )
    return (ret) * (0.5) + 0.25


def static_sample(bounds: np.ndarray) -> np.ndarray:
    """
    Generate two locations outside the bounds

    :param bounds: n x 2 dimenional array containing upper/lower bounds for each dimension
    :return: 2 x n array containing the sampled points
    """
    n = len(bounds)  # Dimensionality of each point
    X = np.zeros((2, n))
    for i in range(n):
        X[0, i] = bounds[i][1] + 5 * (bounds[i][1] - bounds[i][0])
        X[1, i] = bounds[i][0] - 5 * (bounds[i][1] - bounds[i][0])
    return X


class ComparisonGP(GPy.core.Model):
    """
    A class for all common methods needed for the different ComparisonGP wrappers
    """

    def get_current_best(self) -> float:
        """
        :return: minimum of means of predictions at all input locations (needed by q-EI)
        """
        return min(self.Y)

    def get_y_pred(self) -> np.ndarray:
        """
        :return: GP mean at inputs used to compute the posterior approximation (needed by q-EI)
        """
        y_pred, _ = self.predict(self.X, include_likelihood=False)
        return y_pred

    def log_likelihood(self) -> float:
        """
        :return: log marginal likelihood needed for optimizing hyper parameters and performing model comparison
        """
        return self._log_marginal_likelihood

    def predict(
        self, Xnew: np.ndarray, full_cov: bool = False, include_likelihood=True
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predictive mean and covariance of the GP at the input location
        :param Xnew: Locations the prections are wanted at
        :param full_cov: If the user wants the function to return the full covariance or only the diagonal
        :param include_likelihood: If the user wants the function to add the noise of the observations to the prediction covariance
        :return: predictive mean and predictive covariance
        """
        pred_mean, pred_var = self.posterior._raw_predict(
            self.kern, Xnew, self.X, full_cov=full_cov
        )
        if include_likelihood:
            pred_var = pred_var + self.likelihood.variance
        return pred_mean, pred_var

    def predict_noiseless(self, Xnew, full_cov=False) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predictive mean and covariance of the GP latent function at the input location
        :param Xnew: Locations the prections are wanted at
        :param full_cov: If the user wants the function to return the full covariance or only the diagonal
        :return: predictive latent mean and predictive latent covariance
        """
        return self.predict(Xnew, full_cov=full_cov, include_likelihood=False)

    def posterior_samples_f(self, X: np.ndarray, size: int = 10, **predict_kwargs) -> np.ndarray:
        """
        Draw random samples from the posterior predictive distribution

        :param X: Locations where the posterior samples should be drawn at
        :param size: Number of posterior samples
        :return: Simulated posterior samples
        """
        predict_kwargs["full_cov"] = True  # Always use the full covariance for posterior samples.
        predict_kwargs["include_likelihood"] = False
        m, v = self.predict(X, **predict_kwargs)

        def sim_one_dim(m, v):
            # Draw posterior sample in one dimension
            return np.random.multivariate_normal(m, v, size).T

        if self.output_dim == 1:
            return sim_one_dim(m.flatten(), v)[:, np.newaxis, :]
        else:
            fsim = np.empty((X.shape[0], self.output_dim, size))
            for d in range(self.output_dim):
                if v.ndim == 3:
                    fsim[:, d, :] = sim_one_dim(m[:, d], v[:, :, d])
                else:
                    fsim[:, d, :] = sim_one_dim(m[:, d], v)
        return fsim


def comparison_form(y: np.ndarray) -> List[Tuple[int, int]]:
    """
    Transforms the already existing observations to the comparison form

    :param y: function evaluations in a batch
    :return: comparison form for the outputs
    """
    m = len(y)
    assert m > 1
    ind = np.argsort(y.flatten())
    return [(ind[0], ind[i]) for i in range(1, m)]


class ComparisonGPEmukitWrapper(IModel):
    """
    This is a thin wrapper around ComparisonGP to allow users to plug GPy models into Emukit
    """

    def __init__(self, gpy_model: ComparisonGP, batch_size=1):
        """
        :param gpy_model: GPy model object to wrap
        :param batch_size: Number of samples in a batch
        """
        self.model = gpy_model
        self.batch_size = batch_size
        self.g = 0

    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        :param X: (n_points x n_dimensions) array containing locations at which to get predictions
        :return: (mean, variance) Arrays of size n_points x 1 of the predictive distribution at each input location
        """
        return self.model.predict(X)

    def predict_with_full_covariance(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        :param X: (n_points x n_dimensions) array containing locations at which to get predictions
        :return: (mean, variance) Arrays of size n_points x 1 and n_points x n_points of the predictive
                 mean and variance at each input location
        """
        return self.model.predict(X, full_cov=True)

    def set_data(self, X: np.ndarray, Y: np.ndarray) -> None:
        """
        Sets training data in model

        :param X: New training features
        :param Y: New training outputs
        """
        if X.shape[0] > 0:
            X = X[0, :].reshape((1, -1))
            Y = Y[0, :].reshape((-1))
            ind = self.model.X.shape[0]
            X_set = self.model.X
            y_set = self.model.y
            yc_set = self.model.yc
            if X.shape[1] == self.model.X.shape[1]:  # Direct observation
                X_set = np.concatenate((self.model.X, X), axis=0)
                y_set += [(i + ind, Y[i]) for i in range(len(Y))]
            else:
                X_tmp = np.concatenate(
                    tuple(X[:, i * self.batch_size: (i + 1) * self.batch_size] for i in range(len(Y))), axis=0
                )
                X_set = np.concatenate((self.model.X, X_tmp), axis=0)
                yc_set += [[(yc[0] + ind, yc[1] + ind)
                            for yc in comparison_form(Y)]]

            self.model.set_XY(X_set, y_set, yc_set)
        #
        # self.model.set_XY(X, Y)

    def predict_covariance(self, X: np.ndarray, with_noise: bool = True) -> np.ndarray:
        """
        Calculates posterior covariance between points in X
        :param X: Array of size n_points x n_dimensions containing input locations to compute posterior covariance at
        :param with_noise: Whether to include likelihood noise in the covariance matrix
        :return: Posterior covariance matrix of size n_points x n_points
        """
        _, v = self.model.predict(
            X, full_cov=True, include_likelihood=with_noise)
        v = np.clip(v, 1e-10, np.inf)

        return v

    @property
    def X(self) -> np.ndarray:
        """
        :return: An array of shape n_points x n_dimensions containing training inputs
        """
        return np.empty((0, self.model.X.shape[1]))

    @property
    def Y(self) -> np.ndarray:
        """
        :return: An array of shape n_points x 1 containing training outputs
        """
        return np.empty((0, 1))

    def optimize(self):
        """
        Optimizes the model. In this case does nothing since the parameters are fixed
        """
        pass


class AcquisitionFunction:
    """
    This class implements the general AcquisitionFunction

    :param options: Dictionary containing the acquisition function options
    :param optimizer_options: Dictionary containing options for the acquisition function optimizer
    """

    def __init__(self, options: Dict = {}, optimizer_options: Dict = {}):
        self.optimizer_options = optimizer_options
        self.pool_size = options.get("pool_size", -1)
        self.acq_samples = options.get("acq_samples", 1000)
        self.acq_opt_restarts = options.get("acq_opt_restarts", 10)

    def acq_fun_optimizer(
        self, m: ComparisonGP, bounds: np.ndarray, batch_size: int, get_logger: Callable
    ) -> np.ndarray:
        """
        Implements the optimization scheme for the acquisition function

        :param m: The model which posterior is used by the acquisition function (from which the samples are drawn from)
        :param bounds: the optimization bounds of the new sample
        :param batch_size: How many points are there in the batch
        :param get_logger: Function for receiving the legger where the prints are forwarded.
        :return: optimized locations
        """
        raise NotImplementedError

    def reset(self, model: ComparisonGPEmukitWrapper) -> None:
        """
        Some acquisition functions need to be reseted, this method is for that.
        :param model: the model to be passed to the acquisition function (some acquisition functions need a model at this point)
        """
        None


class SequentialThompsonSampler:
    """
    A class for performing Thompson sampling from a GP. The sampler works so that
    it stores the simulated draws and conditions the new draws on (part of) them.

    :param model: A model from which posterior the samples are drawn from
    :param seed: Random seed that specifies the random sample
    :param delta: Defines how close the samples for numerical derivatives are taken from
    :param num_points: Number of points the samples are conditioned on
    """

    def __init__(self, model: ComparisonGP, seed: float = None, delta: float = 1e-5, num_points: int = None):
        self.model = model  # model
        self.posterior = model.posterior

        self.d = self.model.X.shape[1]  # dimensionality of the input points

        self.seeds = []
        self.reset(seed=seed)

        self.delta = delta
        if num_points is None:
            num_points = int(100 * round(np.sqrt(self.d)))
        self.num_points = num_points
        self.scaling = np.array([model.kern.lengthscale[:]]).flatten()

    def reset(self, seed: float = None) -> None:
        """
        Reset the sampler by forgetting the already drawn samples and resetting the seed.

        :param seed: new seed after reset
        """
        self.x_evaluations = np.empty((0, self.model.X.shape[1]))
        self.f_evaluations = np.empty((0, 1))
        if seed is None:
            max = 1000000
            if self.model.name == "MCMC":
                max = self.model.posterior.samples["f"].shape[0]
            seed = np.random.randint(max)
            # Check if we already have used this seed
            while seed in self.seeds:
                seed = np.random.randint(max)
        self.seeds = self.seeds + [seed]
        np.random.seed(seed)

    def add_data(self, x: np.ndarray, f: np.ndarray) -> None:
        """
        Add new points and evaluations to the stack of already evaluated points

        :param x: new locations
        :param f: new evaluations
        """
        self.x_evaluations = np.concatenate((self.x_evaluations, x), axis=0)
        self.f_evaluations = np.concatenate((self.f_evaluations, f), axis=0)

    def get_mu_sigma(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns the posterior predictive distribution at the given locations without conditionin on the already evaluated locatons

        :param x: New locations where the distribution is wanted at
        :return: Tuple containing the predictive mean and covariance
        """
        if self.model.name == "MCMC":
            mu, L = self.posterior._get_mu_L(x, with_index=self.seeds[-1])
            Sigma = L[0, :, :] @ L[0, :, :].T
        else:
            mu, Sigma = self.model.predict_noiseless(x, full_cov=True)
            if len(Sigma.shape) > 2:
                Sigma = Sigma[:, :, 0]
        mu = mu.reshape(-1, 1)
        Sigma = Sigma + 1e-7 * np.eye(Sigma.shape[0])  # noise for robustness
        return mu, Sigma

    def get_posterior_predictive_distribution(
        self, x: np.ndarray, inds: int = np.arange(0)
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns the predictive distribution at the given locations by conditionin on old points and the posterior

        :param x: New location where the distribution is wanted at
        :param inds: indices of already evaluated points the distribution is conditioned with
        :return: Tuple containing the predictive mean and covariance
        """
        n1, n2 = inds.shape[0], x.shape[0]
        mu, Sigma = self.get_mu_sigma(np.concatenate(
            (self.x_evaluations[inds, :].reshape(-1, self.d), x), axis=0))
        if n1 > 0:
            kXX = Sigma[np.ix_(range(n1), range(n1))]
            kxX = Sigma[np.ix_(range(n1, n1 + n2), range(n1))]
            kxx = Sigma[np.ix_(range(n1, n1 + n2), range(n1, n1 + n2))]
            kXX_inv = la.inv(kXX)
            mu_pred = mu[n1:] + \
                kxX @ kXX_inv @ (self.f_evaluations[inds] - mu[:n1])
            Sigma_pred = kxx - kxX @ kXX_inv @ kxX.T
            return mu_pred, Sigma_pred
        else:
            return mu, Sigma

    def get_posterior_predictive_distribution_robust(self, x, num_points=100) -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns the predictive distribution at the given locations by conditionin on old points and the posterior

        :param x: new point the sample is wanted to evaluate at
        :param num_points: number of points taken into account when computing the predictive distribution
        :return: Tuple containing the predictive mean and covariance
        """
        N, n = self.x_evaluations.shape[0], x.shape[0]
        inds = np.arange(N)
        if N >= num_points:
            inds = np.empty((num_points, n), dtype=int)
            for i in range(n):
                dists = np.linalg.norm(
                    (
                        self.x_evaluations
                        - x[
                            None,
                            i,
                            :,
                        ]
                    )
                    / self.scaling[None, :],
                    axis=1,
                )
                inds[:, i] = np.argsort(dists)[:num_points]
            inds = np.unique(inds.flatten())
        return self.get_posterior_predictive_distribution(x, inds=inds)

    def evaluate_and_add(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns the value and gradient of the sample at given point

        :param x: new point the sample is wanted to evaluate at
        :return: Tuple containing the value and gradient
        """
        X = np.atleast_2d(X).reshape((-1, self.d))
        ff, fgrad = np.empty((0)), np.empty((0, self.d))
        for i in range(X.shape[0]):
            # deviate to compute the numerical gradients
            x = np.tile(X[i, :].reshape((1, self.d)), (self.d + 1, 1))
            for i in range(self.d):
                x[i + 1, i] = x[i + 1, i] + self.delta
            # Get predictive distribution
            mu, k = self.get_posterior_predictive_distribution_robust(
                x, num_points=self.num_points)

            # evaluate and add
            f = np.random.multivariate_normal(mu.flatten(), k).reshape((-1, 1))
            self.add_data(x, f)

            # Evaluate numerical gradients
            grad = np.empty((1, self.d))
            for i in range(self.d):
                grad[0, i] = (f[i + 1] - f[0]) / self.delta
            ff = np.concatenate((ff, f[0]), axis=0)
            fgrad = np.concatenate((fgrad, grad), axis=0)
        return ff.reshape((-1, 1)), fgrad


class ThompsonSampling(AcquisitionFunction):
    def acq_fun_optimizer(
        self, m: ComparisonGP, bounds: np.ndarray, batch_size: int, get_logger: Callable
    ) -> np.ndarray:
        """
        Implements the optimization scheme for the Thompson sampling acquisition function

        :param m: The model which posterior is used by the acquisition function (from which the samples are drawn from)
        :param bounds: the optimization bounds of the new sample
        :param batch_size: How many points are there in the batch
        :param get_logger: Function for receiving the legger where the prints are forwarded.
        :return: optimized locations
        """
        self.sampler = SequentialThompsonSampler(m)
        X_all = np.empty((batch_size, m.X.shape[1]))
        for i in range(batch_size):
            self.sampler.reset()  # reset the sampling seed
            yb = np.inf
            Xb = None
            for j in range(self.acq_opt_restarts):
                try:
                    # Initial point of the optimization
                    X0 = random_sample(bounds, 1)
                    res = sp.optimize.minimize(
                        fun=self.sampler.evaluate_and_add,
                        x0=X0.flatten(),
                        method="L-BFGS-B",
                        jac=True,
                        bounds=bounds,
                        options=self.optimizer_options,
                    )
                    X = res.x.reshape(1, len(bounds))
                    y = res.fun
                    if y < yb:
                        yb = y
                        Xb = X
                except Exception as e:
                    get_logger().error("Solver failed. Below the exception\n{}".format(e))
            assert Xb is not None
            X_all[i, :] = Xb
        return X_all

    def reset(self, model: ComparisonGPEmukitWrapper) -> None:
        """
        Some acquisition functions need to be reseted, this method is for that.
        :param m: the GP model which posterior is used
        """
        try:
            self.sampler.reset()
        except:
            self.sampler = SequentialThompsonSampler(model)

    def evaluate(self, x: np.ndarray, model: ComparisonGPEmukitWrapper) -> np.ndarray:
        """
        Computes the Expected Improvement.
        :param x: points where the acquisition is evaluated.
        :param m: the GP model which posterior is used
        :return: acquisition function value
        """
        return self.sampler.evaluate_and_add(x)[0]

    def evaluate_with_gradients(self, x: np.ndarray, model: ComparisonGPEmukitWrapper) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes the Expected Improvement.
        :param x: points where the acquisition is evaluated.
        :param model: the GP model which posterior is used
        :return: A tuple containing the acquisition function values and their gradients
        """
        return self.sampler.evaluate_and_add(x)


def lzip(*args):
    """
    Zip, but returns zipped result as a list.
    """
    return list(zip(*args))


class BlackBoxFunction:
    '''
    All functions to be optimized with BayesianOptimization class
    or DerivativeBayesianOptimization class must inherit this class
    '''

    def __init__(self):
        pass

    def get_dim(self):
        '''
        Should return the size of the input space
        '''
        raise NotImplementedError

    def do_evaluate(self, x):
        '''
        returns the possibly stochastic evaluation for given x
        '''
        raise NotImplementedError

    def do_evaluate_clean(self, x):
        '''
        If possible, returns the noiseless evaluation for given x
        '''
        return None

    def f(self, x):
        raise NotImplementedError


class TestFunction(BlackBoxFunction):
    """
    The base class from which functions of interest inherit.
    """

    __metaclass__ = ABCMeta

    def __init__(self, dim, verify=True):
        assert dim > 0
        self.dim = dim
        self.verify = verify
        self.num_evals = 0
        self.min_loc = None
        self.fmin = None
        self.local_fmin = []
        self.fmax = None
        self.bounds = None
        self.classifiers = []

        self.records = None
        self.noise_std = 0.0
        self.lengths = None

        self.deviation = 1.0
        bounds_array, lengths = self.tuplebounds_2_arrays(
            lzip([0] * self.dim, [1] * self.dim))
        self.us_bounds = bounds_array
        self.lengths = lengths
        self.reset_records()

    def init_normalize_Y(self):
        self.deviation = self.fmax-self.fmin

    def init_normalize_X(self):
        bounds_array, lengths = self.tuplebounds_2_arrays(self.bounds)
        self.lengths = lengths
        self.bounds = lzip([0] * self.dim, [1] * self.dim)
        self.us_bounds = bounds_array
        self.min_loc_01 = (self.min_loc-self.us_bounds[:, 0])/self.lengths

    def tuplebounds_2_arrays(self, bounds):
        bounds_array = np.zeros((self.dim, 2))
        lengths = np.zeros((self.dim))
        for i in range(self.dim):
            bounds_array[i, 0] = bounds[i][0]
            bounds_array[i, 1] = bounds[i][1]
            lengths[i] = bounds[i][1] - bounds[i][0]
        return bounds_array, lengths

    def __repr__(self):
        return '{0}({1})'.format(self.__class__.__name__, self.dim)

    def get_dim(self):
        return self.dim

    def evaluate(self, x):
        if self.verify and (not isinstance(x, np.ndarray) or x.shape != (self.dim,)):
            raise ValueError(
                'Argument must be a np array of length {}'.format(self.dim))

        self.num_evals += 1
        value = self.do_evaluate(x)
        to_be_returned = value.item() if hasattr(value, 'item') else value
        self.update_records(now(), x, to_be_returned)
        # Convert np types to Python types
        return to_be_returned

    def update_records(self, time, location, value):
        self.records['time'].append(time)
        self.records['locations'].append(location)
        self.records['values'].append(value)

    def reset_records(self):
        self.records = {'time': [], 'locations': [], 'values': []}

    def f_c(self, x):
        '''
        returns function values when x is given in  np array of shape N x d where N is number of points and d is dimension
        '''
        x = np.atleast_2d(x)
        y = np.array([(self.do_evaluate_clean((x[i, :]*self.lengths + self.us_bounds[:, 0])
                                              ) - self.fmin)/self.deviation - 1.0 for i in range(x.shape[0])])
        return y.flatten()

    def f(self, x):
        '''
        returns function values when x is given in  np array of shape N x d where N is number of points and d is dimension
        '''

        x = np.atleast_2d(x)
        y = np.array([(self.do_evaluate_clean((x[i, :]*self.lengths + self.us_bounds[:, 0])) - self.fmin)/self.deviation - 1.0
                      + np.random.normal(0, self.noise_std, 1) for i in range(x.shape[0])])
        return y.flatten()

    @abstractmethod
    def do_evaluate(self, x):
        """
        :param x: point at which to evaluate the function
        :type x: np.array with shape (self.dim, )
        """
        raise NotImplementedError

    @abstractmethod
    def do_evaluate_clean(self, x):
        """
        :param x: point at which to evaluate the function
        :type x: np.array with shape (self.dim, )
        """
        return self.do_evaluate(x)


class DataFunction(TestFunction):
    """
    A base class for using data as a function.
    The class takes care of setting up the bounds,
    finding the locations of minimum and maximum
    and interpolating in the points in between the
    data points

    Given the data (X) and observations (Y), forms a function that
    interpolates the values between the provided locations

    :param X: Input locations
    :param Y: Input observations
    """

    def __init__(self, X: np.ndarray, Y: np.ndarray):
        dim = X.shape[1]
        super(DataFunction, self).__init__(dim)

        self.X = X
        self.Y = Y

        self.bounds = lzip(np.min(X, axis=0), np.max(X, axis=0))
        self.min_loc = self.X[np.argmin(self.Y), :]

        # Append corners with score 0
        corners = DataFunction.give_corners(self.bounds)

        self.X = np.r_[self.X, corners]
        self.Y = np.r_[self.Y, np.max(self.Y)*np.ones((corners.shape[0], 1))]
        self.interpolator = sp.interpolate.LinearNDInterpolator(
            self.X, self.Y, fill_value=np.nan)

        self.fmin = np.min(self.Y)
        self.fmax = np.max(self.Y)
        self.classifiers = ['complicated', 'oscillatory', 'unimodal', 'noisy']

    @staticmethod
    def give_corners(bounds: np.ndarray) -> np.ndarray:
        """
        Given the bounds, returns the corners of the hyperrectangle the data just barely fits

        :param bounds: Bounds of the data set (minimum and maximum in every dimension)
        :return: All corners of the dataset
        """
        if len(bounds) > 1:
            corners = DataFunction.give_corners(bounds[1:])
            firsts = np.c_[np.ones((corners.shape[0], 1))
                           * bounds[0][0], corners]
            seconds = np.c_[np.ones((corners.shape[0], 1))
                            * bounds[0][1], corners]
            return np.r_[firsts, seconds]
        else:
            return np.array(bounds[-1]).reshape((-1, 1))

    def do_evaluate(self, x: np.ndarray) -> np.ndarray:
        """
        Evaluates the data function at the given location by interpolating

        :param x: location where the data is wanted to be interpolated
        :return: interpolation result
        """
        return self.interpolator(x)


class Sushi(DataFunction):
    """
    Sushi data as a function : http://www.kamishima.net/sushi/

    :params use_discrete_features: if True, also discrete features of data are used.
    :param num_features: how many of the continuous features are used.
    """

    def __init__(self, use_discrete_features: bool = False, num_features: int = 4):
        # The data files:
        dirname, _ = os.path.split(os.path.abspath(__file__))
        df_features = pd.read_csv(os.path.realpath(os.path.join(
            dirname, "dataset", "sushi", "sushi3.idata")), sep="\t", header=None)
        df_scores = pd.read_csv(os.path.realpath(os.path.join(
            dirname, "dataset", "sushi", "sushi3b.5000.10.score")), sep=" ", header=None)
        # Select the features we want (in the order of importance defined by RBF ARD kernel)
        features = df_features.values[:, [6, 5, 7, 8][:num_features]]
        if use_discrete_features:
            discrete_features = df_features.values[:, [2, 3, 4]]
            features = np.concatenate((features, discrete_features), axis=1)

        # Generate scrores from preferences
        scores = []
        for item_a in range(df_scores.values.shape[1]):
            score = 0
            for item_b in range(df_scores.values.shape[1]):
                if Sushi._prefer_a(item_a, item_b, df_scores):
                    score += 1
            scores.append(score / float(df_scores.values.shape[1]))

        X = features
        # Invert, since we want to find the maximum by BO which finds the minimum
        Y = - np.array(scores).reshape((-1, 1))

        # Scale the data between 0 and 1
        X = (X - np.min(X, axis=0)[None, :]) / \
            (np.max(X, axis=0) - np.min(X, axis=0))[None, :]
        Y = (Y - np.min(Y))/(np.max(Y) - np.min(Y))

        super(Sushi, self).__init__(X, Y)

    @classmethod
    def _prefer_a(cls, item_a: int, item_b: int, df_scores: List):
        """
        Check from data if item_a has higher score that item_b

        :param item_a: index of the first item to be compared
        :param item_b: index of the second item to be compared
        :param df_scores: Scores of all dat points
        :return: True if item_a is preferred over item_b
        """
        ix = (df_scores[item_a].values > -1) * (df_scores[item_b].values > -1)
        prefer_a = np.mean(df_scores[item_a].values[ix]
                           > df_scores[item_b].values[ix])
        prefer_b = np.mean(df_scores[item_b].values[ix]
                           > df_scores[item_a].values[ix])
        return prefer_a > prefer_b


class Noisifier(TestFunction):
    """
    This class dirties function evaluations with Gaussian noise.
    If type == 'add', then the noise is additive; for type == 'mult' the noise is multiplicative.
    sd defines the magnitude of the noise, i.e., the standard deviation of the Gaussian.
    Example: ackley_noise_addp01 = Noisifier(Ackley(3), 'add', .01)
    Obviously, with the presence of noise, the max and min may no longer be accurate.
    """

    def __init__(self, func, noise_type, level, verify=True):
        assert isinstance(func, TestFunction)
        if level <= 0:
            raise ValueError(
                'Noise level must be positive, level={0}'.format(level))
        super(Noisifier, self).__init__(func.dim, verify)
        self.bounds, self.min_loc, self.fmax, self.fmin = func.bounds, func.min_loc, func.fmax, func.fmin
        self.type = noise_type
        self.level = level
        self.func = func
        self.classifiers = list(set(self.classifiers) | set(['noisy']))

    def do_evaluate(self, x):
        if self.type == 'add':
            return self.func.evaluate(x) + self.level * np.random.normal()
        else:
            return self.func.evaluate(x) * (1 + self.level * np.random.normal())

    def __repr__(self):
        return '{0}({1!r}, {2}, {3})'.format(
            self.__class__.__name__,
            self.func,
            self.type,
            self.level,
        )

    def do_evaluate_clean(self, x):
        return self.func.do_evaluate_clean(x)


def nearestPD(A: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Find the nearest positive-definite matrix to input A.
    A Python/Numpy port of John D'Errico's `nearestSPD` MATLAB code [1], which
    credits [2].
    [1] https://www.mathworks.com/matlabcentral/fileexchange/42885-nearestspd
    [2] N.J. Higham, "Computing a nearest symmetric positive semidefinite
    matrix" (1988): https://doi.org/10.1016/0024-3795(88)90223-6

    :param A: A square matrix
    :return: A Tuple containing the positive definite version of A and a float
                 indicating how much jitter was added to the diagonal of A
                 to make it positive definite
    """

    B = (A + A.T) / 2
    _, s, V = la.svd(B)

    H = np.dot(V.T, np.dot(np.diag(s), V))

    A2 = (B + H) / 2

    A3 = (A2 + A2.T) / 2

    k = 1
    if isPD(A3):
        return A3, 0

    spacing = np.spacing(la.norm(A))
    # The above is different from [1]. It appears that MATLAB's `chol` Cholesky
    # decomposition will accept matrixes with exactly 0-eigenvalue, whereas
    # Numpy's will not. So where [1] uses `eps(mineig)` (where `eps` is Matlab
    # for `np.spacing`), we use the above definition. CAVEAT: our `spacing`
    # will be much larger than [1]'s `eps(mineig)`, since `mineig` is usually on
    # the order of 1e-16, and `eps(1e-16)` is on the order of 1e-34, whereas
    # `spacing` will, for Gaussian random matrixes of small dimension, be on
    # othe order of 1e-16. In practice, both ways converge, as the unit test
    # below suggests.
    I = np.eye(A.shape[0])

    mineig = 0.0
    while not isPD(A3):
        mineig = np.min(np.real(la.eigvals(A3)))
        A3 += I * (-mineig * k**2 + spacing)
        k += 1
        if (k > 10):
            break
    return A3, -mineig * k**2 + spacing


def isPD(B: np.ndarray) -> bool:
    """
    Returns true when input is positive-definite, via Cholesky

    :param B: a square matrix
    :return: A boolean value indicating if B is positive definite
    """
    try:
        _ = la.cholesky(B)
        return True
    except la.LinAlgError:
        return False


class MarginalMoments(object):
    """
    A simple container for the marginal moments
    :param num_data: how many observations are there
    """

    def __init__(self, num_data):
        self.logZ_hat = np.empty(num_data, dtype=np.float64)
        self.mu_hat = np.empty(num_data, dtype=np.float64)
        self.sigma2_hat = np.empty((num_data, num_data), dtype=np.float64)


class GaussianApproximation(object):
    """
    A simple container for Gaussian approximations of the batches
    :param v: scale
    :param tau: precision
    """

    def __init__(self, v, tau):
        self.v = v
        self.tau = tau

    def _update_batch(
        self,
        eta: float,
        delta: float,
        post_params: posteriorParams,
        marg_moments: MarginalMoments,
        batch: List[int],
        get_logger: Callable = None,
        sigma2s: np.ndarray = None,
    ):
        """
        Computes new gaussian approximation for a batch given posterior and marginal moments. See e.g. 3.59 in http://www.gaussianprocess.org/gpml/chapters/RW.pdf
        :param eta: parameter for fractional updates.
        :param delta: damping updates factor.
        :param post_params: Posterior approximation
        :param marg_moments: Marginal moments at this iteration
        :param batch: list of indices of the parameters to be updated
        :param get_logger: Function for receiving the legger where the prints are forwarded.
        """
        sigma_hat_inv, _, _, _ = pdinv(
            marg_moments.sigma2_hat[np.ix_(batch, batch)])
        post_sigma_inv, _, _, _ = pdinv(
            post_params.Sigma[np.ix_(batch, batch)])

        tmp0 = sigma_hat_inv - post_sigma_inv

        delta_tau = delta / eta * tmp0
        delta_v = (
            delta
            / eta
            * (np.dot(marg_moments.mu_hat[batch], sigma_hat_inv) - np.dot(post_params.mu[batch], post_sigma_inv))
        )
        tau_tilde_prev = self.tau[np.ix_(batch, batch)]
        tmp = (1 - delta) * self.tau[np.ix_(batch, batch)] + delta_tau

        # Let us umake sure that sigma_hat_inv-post_sigma_inv is positive definite
        tmp, added_value = nearestPD(tmp)
        update = True
        if (added_value > 1) and (sigma2s is not None):
            update = False
            sigma2s *= 1.05
            if get_logger is not None:
                get_logger().error(
                    "Increasing batch noise. Not updating gaussian approximation ({})".format(
                        sigma2s[0])
                )
        if update:
            self.tau[np.ix_(batch, batch)] = tmp
            self.v[batch] = (1 - delta) * self.v[batch] + delta_v
        return (delta_tau, delta_v), sigma2s


class CavityParams(object):
    """
    A simple container for the cavity parameters
    :param num_data: how many observations are there
    """

    def __init__(self, num_data: int):
        self.v = np.zeros(num_data, dtype=np.float64)
        self.tau = np.zeros((num_data, num_data), dtype=np.float64)

    def _update_i(self, eta: float, ga_approx: GaussianApproximation, post_params: posteriorParams, i: int):
        """
        Computes the cavity params for specific index
        :param eta: parameter for fractional updates.
        :param ga_approx: Gaussian approximation
        :param post_params: Posterior approximation
        :param i: index of the parameters to be updated
        """
        self.tau[i, i] = 1.0 / post_params.Sigma[i, i] - \
            eta * ga_approx.tau[i, i]
        self.v[i] = post_params.mu[i] / \
            post_params.Sigma[i, i] - eta * ga_approx.v[i]

    def _update_batch(
        self,
        eta: float,
        ga_approx: GaussianApproximation,
        post_params: posteriorParams,
        batch: List[int],
        get_logger: Callable = None,
    ):
        """
        Computes the cavity params for specific batch
        :param eta: parameter for fractional updates.
        :param ga_approx: Gaussian approximation
        :param post_params: Posterior approximation
        :param batch: list of indices of the parameters to be updated
        :param get_logger: Function for receiving the legger where the prints are forwarded.
        """
        post_sigma_inv = inv(post_params.Sigma[np.ix_(batch, batch)])
        tmp = post_sigma_inv - eta * ga_approx.tau[np.ix_(batch, batch)]
        self.tau[np.ix_(batch, batch)], _ = nearestPD(tmp)
        self.v[batch] = np.dot(
            post_sigma_inv, post_params.mu[batch]) - eta * ga_approx.v[batch]


def posdef_sqrtm(M: np.ndarray) -> np.ndarray:
    """
    Returns a square root of a positive definite matrix
    :param M: A positive definite matrix
    :return: Squarte root of M
    """
    (U, S, VT) = svd(M)
    D = np.diag(np.sqrt(S))
    return U @ D @ VT


def sqrtm_block(M: np.ndarray, y: List[Tuple[int, float]], yc: List[List[Tuple[int, int]]]) -> np.ndarray:
    """
    Returns a square root of a positive definite matrix
    :param M: A positive definite block matrix
    :param y: Observations indicating where we have a diagonal element
    :param yc: Comparisons indicating where we have a block diagonal element
    :return: Squarte root of M
    """
    Msqrtm = np.zeros(M.shape)
    if len(y) > 0:
        for yi, yval in y:
            Msqrtm[yi, yi] = np.sqrt(M[yi, yi])
    if len(yc) > 0:
        for ycb in yc:
            loc_inds_winners, loc_inds_loosers = [ycb[k][0] for k in range(len(ycb))], [
                ycb[k][1] for k in range(len(ycb))
            ]
            batch = np.sort(np.unique(loc_inds_winners + loc_inds_loosers))
            Msqrtm[np.ix_(batch, batch)] = posdef_sqrtm(
                M[np.ix_(batch, batch)])
    return Msqrtm


def update_posterior(
    K: np.ndarray,
    v: np.ndarray,
    tau: np.ndarray,
    y: List[Tuple[int, float]],
    yc: List[List[Tuple[int, int]]],
    jitter: float = 1e-9,
    get_logger: Callable = None,
) -> posteriorParams:
    """
    Update the posterior approximation. See e.g. 3.59 in http://www.gaussianprocess.org/gpml/chapters/RW.pdf
    :param K: prior covariance matrix
    :param v: Scale of the Gaussian approximation
    :param tau: Precision of the Gaussian approximation
    :param y: Observations indicating where we have a diagonal element
    :param yc: Comparisons indicating where we have a block diagonal element
    :param jitter: small number added to the diagonal to increase robustness.
    :param get_logger: Function for receiving the legger where the prints are forwarded.
    :return: posterior approximation
    """
    D = K.shape[0]
    sqrt_tau = sqrtm_block(tau + np.diag(jitter * np.ones((D))), y, yc)
    G = np.dot(sqrt_tau, K)
    B = np.identity(D) + np.dot(G, sqrt_tau)
    L = jitchol(B)
    V = np.linalg.solve(L, G)
    Sigma_full = K - np.dot(V.T, V)
    mu = np.dot(Sigma_full, v)
    Sigma = np.diag(Sigma_full)

    return posteriorParams(mu=mu, Sigma=Sigma_full, L=L)


def _compute_moments_sampling(
    mf: np.ndarray,
    vf: np.ndarray,
    ind_winners: List[int],
    ind_loosers: List[int],
    nu2: np.ndarray,
    N: int = 10000,
    get_logger: Callable = None,
) -> Tuple[float, np.ndarray, np.ndarray]:
    """
    Compute the marginal moments of a batch using numerical integration
    :param mf: cavity mean of the batch
    :params vf: cavity covariance of the batch
    :params ind_winners: indices of comparison winners
    :params ind_loosers: indices of comparison loosers
    :param nu2: noise variance of the batch members
    :param N: number of samples used for approximating the moments
    :param get_logger: Function for receiving the logger where the prints are forwarded.
    :return: Tuple containing the integral, first and second moments
    """
    m = vf.shape[0]
    sqrt_nu = np.sqrt(nu2)

    f = np.random.multivariate_normal(mf, vf, N)

    # Generate samples to compute likelihood
    if not (np.prod(ind_winners == ind_winners[0]) == 1):  # batch winner case
        return

    ind_winner = ind_winners[0]
    s = f[:, ind_winner] + sqrt_nu[ind_winner] * np.random.randn(N)
    def phi(x): return norm.cdf(x)
    s_compare = phi((f[:, ind_loosers] - s[:, None]) /
                    sqrt_nu[None, ind_loosers, 0])
    s_compare = np.exp(np.log(s_compare).sum(axis=1))
    likelihood = s_compare.copy()
    qs0_ = np.mean(likelihood)
    qs0_ = max([qs0_, 1e-9])

    # First moments:
    f_nonzero = likelihood[:, None] * f
    likelihood_sqrt = np.sqrt(likelihood)
    f_nonzero_sqrt = likelihood_sqrt[:, None] * f
    qs1_ = np.sum(f_nonzero, axis=0) / qs0_ / N

    # Second moments
    diff_f = f_nonzero_sqrt - qs1_[None, :] * likelihood_sqrt[:, None]
    qs2_ = diff_f.T @ diff_f / qs0_ / N

    return qs0_, qs1_, qs2_


def _match_moments_batch(
    v_cav: np.ndarray,
    tau_cav: np.ndarray,
    ind_winners: List[int],
    ind_loosers: List[int],
    nu2: np.ndarray,
    N: int = 10000,
    get_logger: Callable = None,
) -> Tuple[int, np.ndarray, np.ndarray]:
    """
    Computes the moments of the given batch
    :param v_cav: Scale of the cavity distribution
    :param tau_cav: Precision of the cavity distribution
    :param ind_winners: Indices of winners in each pairwise comparison of the batch
    :param ind_loosers: Indices of loosers in each pairwise comparison of the batch
    :param nu2: Noise variance of each batch member likelihood
    :param N: Number of parameters used to compute the moments
    :param get_logger: Function for receiving the legger where the prints are forwarded.
    :return: Tuple containing the integral, mean and variance
    """
    n = tau_cav.shape[0]
    tau_cav_inv = inv(tau_cav)
    m_cav, sigma_cav = np.dot(v_cav, tau_cav_inv), tau_cav_inv
    logZ, site_m, site_m2 = _compute_moments_sampling(
        m_cav, sigma_cav, ind_winners, ind_loosers, nu2, N=N, get_logger=get_logger
    )

    min_eig0 = np.min(np.real(la.eig(site_m2)[0]))
    if min_eig0 < 0:
        site_m2 -= min_eig0 * np.eye(site_m2.shape[0])
        if get_logger is not None:
            get_logger().error(
                "marginal moment not suitable in moment matching, adding smallest eigenvalue ({}) to the diagonal to guarantee PD".format(
                    -1 * min_eig0
                )
            )

    if np.isnan(logZ) or np.any(np.isnan(site_m)) or np.any(np.isnan(site_m2)):
        raise AssertionError()
    return (
        np.array([logZ / n for i in range(n)]),
        site_m.reshape(
            n,
        ),
        site_m2,
        nu2,
    )


def _log_Z_tilde(
    marg_moments: MarginalMoments,
    ga_approx: GaussianApproximation,
    cav_params: CavityParams,
    y: List[Tuple[int, float]],
    yc: List[List[Tuple[int, int]]],
) -> float:
    """
    Give the log marginal likelihood of the posterior approximation
    :param marg_moments: Marginal moments of the posterior
    :param ga_approx: Gaussian approximation of the batches
    :param cav_params: Cavity parameters of the posterior
    :param y: Direct observations as a list of tuples telling location index (row in X) and observation value.
    :param yc: Batch comparisons in a list of lists of tuples. Each batch is a list and tuples tell the comparisons (winner index, loser index)
    :return: log marginal likleihood of the posterior
    """

    # go through direct observations:
    inds = [np.array([y[i][0]]) for i in range(len(y))]  # direct observations
    for d in range(len(yc)):  # iterate through batches
        loc_inds_winners, loc_inds_loosers = [yc[d][k][0] for k in range(len(yc[d]))], [
            yc[d][k][1] for k in range(len(yc[d]))
        ]
        inds += [np.sort(np.unique(loc_inds_winners + loc_inds_loosers))]
    log_Z_tilde = np.sum(marg_moments.logZ_hat + 0.5 * np.log(2 * np.pi))
    for ind in inds:
        log_Z_tilde += (
            0.5
            * np.log(
                np.linalg.det(
                    np.eye(len(
                        ind)) + np.dot(ga_approx.tau[np.ix_(ind, ind)], inv(cav_params.tau[np.ix_(ind, ind)]))
                )
            )
            - 0.5
            * np.linalg.multi_dot(
                [
                    ga_approx.v[ind].T,
                    inv(cav_params.tau[np.ix_(ind, ind)] +
                        ga_approx.tau[np.ix_(ind, ind)]),
                    ga_approx.v[ind],
                ]
            )
            + 0.5
            * np.linalg.multi_dot(
                [
                    cav_params.v[ind].T,
                    inv(cav_params.tau[np.ix_(ind, ind)] +
                        ga_approx.tau[np.ix_(ind, ind)]),
                    np.linalg.multi_dot(
                        [ga_approx.tau[np.ix_(ind, ind)], inv(
                            cav_params.tau[np.ix_(ind, ind)]), cav_params.v[ind]]
                    )
                    - 2.0 * ga_approx.v[ind],
                ]
            )
        )
    return log_Z_tilde


log_2_pi = np.log(2 * np.pi)


def _ep_marginal(
    K: np.ndarray,
    ga_approx: GaussianApproximation,
    Z_tilde: float,
    y: List[Tuple[int, float]],
    yc: List[List[Tuple[int, int]]],
) -> Tuple[float, posteriorParams]:
    """
    Compute Gaussian log marginal and posterior
    :param K: prior covariance matrix
    :param ga_approx: Gaussian approximation of the batches
    :param Z_tilde: log marginal of the posterior
    :param y: Direct observations as a list of tuples telling location index (row in X) and observation value.
    :param yc: Batch comparisons in a list of lists of tuples. Each batch is a list and tuples tell the comparisons (winner index, loser index)
    """
    post_params = update_posterior(K, ga_approx.v, ga_approx.tau, y, yc)

    # Gaussian log marginal excluding terms that can go to infinity due to arbitrarily small tau_tilde.
    # These terms cancel out with the terms excluded from Z_tilde
    B_logdet = np.sum(2.0 * np.log(np.diag(post_params.L)))
    log_marginal = 0.5 * (
        -len(ga_approx.v) * log_2_pi - B_logdet +
        np.sum(ga_approx.v * np.dot(post_params.Sigma, ga_approx.v))
    )
    log_marginal += Z_tilde

    return log_marginal, post_params


def _inference(
    K: np.ndarray,
    ga_approx: GaussianApproximation,
    cav_params: CavityParams,
    Z_tilde: float,
    y: List[Tuple[int, float]],
    yc: List[List[Tuple[int, int]]],
) -> Tuple[PosteriorEP, int, Dict]:
    """
    Compute the posterior approximation
    :param K: prior covariance matrix
    :param ga_approx: Gaussian approximation of the batches
    :param cav_params: Cavity parameters of the posterior
    :param Z_tilde: Log marginal likelihood
    :param y: Direct observations as a list of tuples telling location index (row in X) and observation value.
    :param yc: Batch comparisons in a list of lists of tuples. Each batch is a list and tuples tell the comparisons (winner index, loser index)
    :return: A tuple consisting of the posterior approximation, log marginal likelihood and gradient dictionary
    """

    log_marginal, post_params = _ep_marginal(K, ga_approx, Z_tilde, y, yc)
    tau_tilde_root = sqrtm_block(ga_approx.tau, y, yc)
    Sroot_tilde_K = np.dot(tau_tilde_root, K)
    aux_alpha, _ = dpotrs(post_params.L, np.dot(
        Sroot_tilde_K, ga_approx.v), lower=1)
    alpha = (ga_approx.v - np.dot(tau_tilde_root, aux_alpha)
             )[:, None]  # (K + Sigma^(\tilde))^(-1) /mu^(/tilde)
    LWi, _ = dtrtrs(post_params.L, tau_tilde_root, lower=1)

    Wi = np.dot(LWi.T, LWi)
    symmetrify(Wi)  # (K + Sigma^(\tilde))^(-1)
    dL_dK = 0.5 * (tdot(alpha) - Wi)
    dL_dthetaL = 0
    return (
        PosteriorEP(woodbury_inv=np.asfortranarray(
            Wi), woodbury_vector=alpha, K=K),
        log_marginal,
        {"dL_dK": dL_dK, "dL_dthetaL": dL_dthetaL, "dL_dm": alpha},
    )


def ep_comparison(
    X: np.ndarray,
    y: List[Tuple[int, float]],
    yc: List[List[Tuple[int, int]]],
    kern: GPy.kern.Kern,
    sigma2s: np.ndarray,
    max_itt: int = 50,
    delta: float = 0.9,
    eta: float = 1.0,
    tol: float = 1e-6,
    ga_approx_old: GaussianApproximation = None,
    get_logger: Callable = None,
) -> Tuple[PosteriorEP, int, Dict, GaussianApproximation]:
    """
    :param X: All locations of both direct observations and batch comparisons
    :param y: Direct observations as a list of tuples telling location index (row in X) and observation value.
    :param yc: Batch comparisons in a list of lists of tuples. Each batch is a list and tuples tell the comparisons (winner index, loser index)
    :param kern: GP kernel
    :param sigma2s: noise variance of observations
    :param max_itt: maximum number of iterations
    :param delta: damping updates factor.
    :param eta: parameter for fractional updates.
    :param tol: tolerance after which the EP is stopped unless too many iterations have passed
    :param ga_approx_old: If there has been previous gaussian approximation, it should be passed
    :param get_logger: Function for receiving the legger where the prints are forwarded.
    :return: A tuple consisting of the posterior approximation, log marginal likelihood, radient dictionary and gaussian approximations of the batches
    """

    t0 = time.time()

    N = X.shape[0]
    Ndir = len(y)
    Ncomp = len(yc)
    ###################################################################################
    # Contruct observations and kernels
    ###################################################################################
    K = kern.K(X)

    ###################################################################################
    # Prepare marginal moments, site approximation and cavity containers
    ###################################################################################

    f_marg_moments = MarginalMoments(N)
    f_ga_approx = GaussianApproximation(
        np.zeros(N, dtype=np.float64), np.zeros((N, N), dtype=np.float64))
    f_cavity = CavityParams(N)

    # insert likelihood information to each gaussian approximation
    for i in range(Ndir):
        (ii, yi) = y[i]  # index in kernel, y value
        f_ga_approx.v[ii] = yi / sigma2s[i]
        f_ga_approx.tau[ii, ii] = 1.0 / sigma2s[i]

    if ga_approx_old is not None:  # If there exists old gaussian approximation, we reuse it
        N_old = ga_approx_old.tau.shape[0]
        if N - N_old > -1:
            f_ga_approx.v[:N_old] = ga_approx_old.v
            f_ga_approx.tau[np.ix_(
                np.arange(N_old), np.arange(N_old))] = ga_approx_old.tau

    ###################################################################################
    # Prepare global approximations
    ###################################################################################
    f_post_params = update_posterior(K, f_ga_approx.v, f_ga_approx.tau, y, yc)
    if np.any(np.isnan(f_post_params.mu)):
        if get_logger is not None:
            get_logger().error("Posterior mean contains nan in the EP approximation")

    ###################################################################################
    # Iterate
    ###################################################################################
    for itt in range(max_itt):
        old_params = np.hstack(
            (f_post_params.mu.copy(), f_post_params.Sigma_diag.copy()))

        if get_logger is not None:
            get_logger().info("Iteration %d" % (itt + 1))
        d_list = []
        if len(yc) > 0:
            d_list = np.random.choice(
                range(len(yc)), size=len(yc), replace=False)
        for d in d_list:  # iterate through batches
            loc_inds_winners, loc_inds_loosers = [yc[d][k][0] for k in range(len(yc[d]))], [
                yc[d][k][1] for k in range(len(yc[d]))
            ]
            loc_inds_batch = np.sort(
                np.unique(loc_inds_winners + loc_inds_loosers))
            # get relevant EP parameters for comparison points
            f_cavity._update_batch(
                eta=eta, ga_approx=f_ga_approx, post_params=f_post_params, batch=loc_inds_batch, get_logger=get_logger
            )

            try:
                # get cavity parameters of the batch
                ind_winners, ind_loosers = [np.where(loc_inds_batch == it)[0][0] for it in loc_inds_winners], [
                    np.where(loc_inds_batch == it)[0][0] for it in loc_inds_loosers
                ]  # indices within a batch
                (
                    f_marg_moments.logZ_hat[loc_inds_batch],
                    f_marg_moments.mu_hat[loc_inds_batch],
                    f_marg_moments.sigma2_hat[np.ix_(
                        loc_inds_batch, loc_inds_batch)],
                    sigma2s[loc_inds_batch],
                ) = _match_moments_batch(
                    f_cavity.v[loc_inds_batch],
                    f_cavity.tau[np.ix_(loc_inds_batch, loc_inds_batch)],
                    ind_winners,
                    ind_loosers,
                    sigma2s[loc_inds_batch],
                    N=100000,
                    get_logger=get_logger,
                )
            except AssertionError as e:
                if get_logger is not None:
                    get_logger().error(
                        "Numerical problem with feedback %d in iteration %d. Skipping update" % (d, itt))
            _, sigma2s[loc_inds_batch] = f_ga_approx._update_batch(
                eta=eta,
                delta=delta,
                post_params=f_post_params,
                marg_moments=f_marg_moments,
                batch=loc_inds_batch,
                get_logger=get_logger,
                sigma2s=sigma2s[loc_inds_batch],
            )
        f_post_params = update_posterior(
            K, f_ga_approx.v, f_ga_approx.tau, y, yc, get_logger=get_logger)

        if np.any(np.isnan(f_post_params.mu)) or np.any(np.isnan(f_post_params.mu)):
            if get_logger is not None:
                get_logger().error("Posterior mean contains nan in the EP approximation")

        # check for convergence
        new_params = np.hstack(
            (f_post_params.mu.copy(), f_post_params.Sigma_diag.copy()))
        converged = True
        if np.mean((new_params - old_params) ** 2) / np.mean(old_params**2) < tol:
            pass
        else:
            converged = False
        if converged:
            run_time = time.time() - t0
            if get_logger is not None:
                get_logger().info("Converged in %d iterations in %4.3fs" % (itt + 1, run_time))
            break
    # 3
    # Marginal likelihood & gradients
    # 3

    def log_npdf(x, m, v): return -0.5 * \
        np.log(2 * np.pi * v) - (x - m) ** 2 / (2 * v)

    # compute normalization constant for likelihoods
    for i in range(Ndir):
        (ii, yi) = y[i]  # index in kernel, y value
        f_cavity._update_i(eta=eta, ga_approx=f_ga_approx,
                           post_params=f_post_params, i=ii)
        f_marg_moments.logZ_hat[ii] = log_npdf(
            yi, f_cavity.v[ii] / f_cavity.tau[ii, ii], 1.0 /
            f_cavity.tau[ii, ii] + sigma2s[i]
        )

    # marginal likelihood and gradient contribution from each f

    Z_tilde = _log_Z_tilde(f_marg_moments, f_ga_approx, f_cavity, y, yc)
    f_posterior, f_logZ, f_grad = _inference(
        K, f_ga_approx, f_cavity, Z_tilde, y, yc)
    return f_posterior, f_logZ, f_grad, f_ga_approx


class EPComparisonGP(ComparisonGP):
    """
    GPy wrapper for a GP model consisting of preferential batch observations when the posterior is approximated using Expectation Propagation
    :param X: All locations of both direct observations and batch comparisons
    :param y: Direct observations in as a list of tuples telling location index (row in X) and observation value.
    :param yc: Batch comparisons in a list of lists of tuples. Each batch is a list and tuples tell the comparisons (winner index, loser index)
    :param kernel: A GPy kernel used
    :param likelihood: A GPy likelihood. Only Gaussian likelihoods are accepted
    :param name: Name of the model. Defaults to 'EpComparisonGP'
    :param ep_max_it: Maximum number of iterations used when approximating the posterior in EP.
    :param eta: parameter for fractional EP updates.
    :param delta: damping EP updates factor.
    :param get_logger: Function for receiving the legger where the prints are forwarded.
    """

    def __init__(
        self,
        X: np.ndarray,
        y: List[Tuple[int, float]],
        yc: List[List[Tuple[int, int]]],
        kernel: GPy.kern.Kern,
        likelihood: GPy.likelihoods.Gaussian,
        name: str = "EPComparisonGP",
        ep_max_itt: int = 100,
        delta: float = 0.5,
        eta: float = 0.5,
        get_logger: Callable = None,
    ):

        super(EPComparisonGP, self).__init__(name=name)

        self.N, self.D = X.shape[0], X.shape[1]

        self.output_dim = 1  # hard coded, the code doesn't support multi output case

        self.X = X
        self.y = y
        self.yc = yc

        self.kern = kernel
        self.likelihood = likelihood

        # A helper parameter for EP. Each observation could possibly come from different kernels and likelihoods.
        # The inference supports this already, but this GPy wrapper doesn't
        self.sigma2s = self.likelihood.variance * \
            np.ones((X.shape[0], 1), dtype=int)

        self.ep_max_itt = ep_max_itt
        self.eta = eta
        self.delta = delta

        self.link_parameter(self.kern)
        self.link_parameter(self.likelihood)
        self.posterior, self.ga_approx, self.Y = None, None, None
        self.get_logger = get_logger

    def parameters_changed(self):
        """
        Update the posterior approximation after kernel or likelihood parameters have changed or there are new observations
        """
        # Recompute the posterior approximation
        self.posterior, self._log_marginal_likelihood, self.grad_dict, self.ga_approx = ep_comparison(
            self.X,
            self.y,
            self.yc,
            self.kern,
            self.sigma2s,
            max_itt=self.ep_max_itt,
            tol=1e-6,
            delta=self.delta,
            eta=self.eta,
            ga_approx_old=self.ga_approx,
            get_logger=self.get_logger,
        )

        # predict Y at inputs (needed by q-EI)
        self.Y = self.get_y_pred()

    def set_XY(self, X: np.ndarray, y: List[Tuple[int, float]], yc: List[List[Tuple[int, int]]]):
        """
        Set new observations and recompute the posterior
        :param X: All locations of both direct observations and batch comparisons
        :param y: Direct observations in as a list of tuples telling location index (row in X) and observation value.
        :param yc: Batch comparisons in a list of lists of tuples. Each batch is a list and tuples tell the comparisons (winner index, loser index)
        """
        self.X = X
        self.y = y
        self.yc = yc
        self.sigma2s = self.likelihood.variance * \
            np.ones((X.shape[0], 1), dtype=int)
        self.parameters_changed()


def configure_logger(log_file=None) -> None:
    """
    Configures the file the prints are forwarded to

    :param log_file: The file the prints are forwarded to
    """
    if log_file is None:
        logger = logging.getLogger("logger.log")  # default logger
        file_handler = logging.StreamHandler()
    else:
        logger = logging.getLogger(log_file)
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)-8s \n %(message)s")
        file_handler = logging.FileHandler(log_file, mode="w")
        file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False


def give_comparisons(func: Callable, points: np.ndarray, si: int = 0) -> List[List[Tuple[int, int]]]:
    """
    Evaluates the function in given batch and returns the batch winner in a form accepted by the inference algorithms

    :param func: the black box objective
    :param points: batch locations
    :param si: starting index of the batch (the number of points evaluated so far)
    :return: Compar
    """
    ind = np.random.permutation(points.shape[0])
    y = func(points).reshape((-1, 1))
    s1, s2 = ind[::2], ind[1::2]
    return [[(s1[i] + si, s2[i] + si)] if y[s1[i]] < y[s2[i]] else [(s1[i] + si, s2[i] + si)] for i in range(len(s1))]


class EmukitAcquisitionFunctionWrapper(Acquisition):
    def __init__(self, model: ComparisonGP, acquisitionFunction: AcquisitionFunction) -> None:
        """
        This acquisition computes for a given input the improvement over the current best observed value in
        expectation. For more information see:
        Efficient Global Optimization of Expensive Black-Box Functions
        Jones, Donald R. and Schonlau, Matthias and Welch, William J.
        Journal of Global Optimization
        :param model: model that is used to compute the improvement.
        :param acquisitionFunction: The used acquisitionFunction
        """

        self.model = model
        self.acquisitionFunction = acquisitionFunction
        self.size = self.model.X.shape[0]

    def evaluate(self, x: np.ndarray) -> np.ndarray:
        """
        Computes the Expected Improvement.
        :param x: points where the acquisition is evaluated.
        :return: acquisition function values
        """
        return -self.acquisitionFunction.evaluate(x, self.model)

    def evaluate_with_gradients(self, x: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes the Expected Improvement.
        :param x: points where the acquisition is evaluated.
        :return: a tuple containing the acquisition function values and their gradients
        """
        f, g = self.acquisitionFunction.evaluate_with_gradients(x, self.model)
        return -f, -g

    def reset(self, model: ComparisonGPEmukitWrapper) -> None:
        """
        Some acquisition functions need to be reseted, this method is for that.
        :param model: the model to be passed to the acquisition function (some acquisition functions need a model at this point)
        """
        self.acquisitionFunction.reset(model.model)

    @property
    def has_gradients(self) -> bool:
        """
        :return: True as all acquisition functions have gradients
        """
        return True


class SequentialGradientAcquisitionOptimizer(GradientAcquisitionOptimizer):
    def __init__(self, space: ParameterSpace, batch_size: int) -> None:
        """
        :param space: The parameter space spanning the search problem.
        """
        self.batch_size = batch_size
        super().__init__(space)

    def _optimize(self, acquisition: Acquisition, context_manager: ContextManager) -> Tuple[np.ndarray, np.ndarray]:
        """
        Implementation of abstract method.
        Taking into account gradients if acquisition supports them.
        See AcquisitionOptimizerBase._optimizer for parameter descriptions.
        See class docstring for implementation details.
        """
        x_min, fx_min = None, None
        for i in range(self.batch_size):
            acquisition.reset(acquisition.model)
            x_min_i, fx_min_i = super()._optimize(acquisition, context_manager)

            if x_min is None:
                x_min, fx_min = x_min_i, fx_min_i
            else:
                x_min, fx_min = np.concatenate(
                    (x_min, x_min_i), axis=1), fx_min + fx_min_i
        return x_min, fx_min

    def optimize(self, acquisition: Acquisition, context: Optional = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Optimizes the acquisition function.
        :param acquisition: The acquisition function to be optimized
        :param context: Optimization context.
                        Determines whether any variable values should be fixed during the optimization
        :return: Tuple of (location of maximum, acquisition value at maximizer)
        """
        if context is None:
            context = dict()
        else:
            self._validate_context_parameters(context)
        context_manager = ContextManager(self.space, context)
        max_x, max_value = self._optimize(acquisition, context_manager)

        # Optimization might not match any encoding exactly
        # Rounding operation here finds the closest encoding
        rounded_max_x = np.concatenate(
            tuple(
                self.space.round(
                    max_x[:, i * self.batch_size: (i + 1) * self.batch_size])
                for i in range(self.batch_size)
            ),
            axis=1,
        )

        return max_x, max_value


def create_bayesian_optimization_loop(
    gpy_model: ComparisonGP, lims: np.array, batch_size: int, acquisition: AcquisitionFunction
) -> BayesianOptimizationLoop:
    """
    Creates Bayesian optimization loop for Bayesian neural network or random forest models.
    :param gpy_model: the GPy model used in optimization
    :param lims: Optimization limits for the inputs
    :param batch_size: number of observations used in batch
    :param acquisition: acquisition function used in the bayesian optimization
    :return: emukit BO loop
    """

    # Create model
    model = ComparisonGPEmukitWrapper(gpy_model, batch_size)

    # Create acquisition
    emukit_acquisition = EmukitAcquisitionFunctionWrapper(model, acquisition)

    if type(emukit_acquisition.acquisitionFunction) is ThompsonSampling:
        parameter_space = []
        for j in range(len(lims)):
            parameter_space += [ContinuousParameter(
                "x{}".format(j), lims[j][0], lims[j][1])]
        parameter_space = ParameterSpace(parameter_space)
        acquisition_optimizer = SequentialGradientAcquisitionOptimizer(
            parameter_space, batch_size)
    else:
        parameter_space = []
        for k in range(batch_size):
            for j in range(len(lims)):
                parameter_space += [ContinuousParameter(
                    "x{}{}".format(k, j), lims[j][0], lims[j][1])]
        parameter_space = ParameterSpace(parameter_space)
        acquisition_optimizer = GradientAcquisitionOptimizer(parameter_space)

    bo = BayesianOptimizationLoop(
        model=model, space=parameter_space, acquisition=emukit_acquisition)
    return BayesianOptimizationLoop(
        model=model, space=parameter_space, acquisition=emukit_acquisition, acquisition_optimizer=acquisition_optimizer
    )


class BayesianOptimization:
    """
    This is a simple implementation of Bayesian optimization needed for preforming preferential batch Bayesian optimization

    The class structure is heavily inspired by https://github.com/oxfordcontrol/Bayesian-Optimization/blob/GPy-based/methods/bo.py

    :param options: a dictionary containing otions needed by the BO loop.
                    The dictionary must contain values for 'objective' (type: TestFunction),
                    'inference' (type: CompartisonGP), 'acquisition' (type: AcquisitionFunction),
                    'kernel' (type: GPy.kern.Kern) and 'batch_size' (type:int)
    """

    def __init__(self, options: Dict):
        self.options = options.copy()

        # GPy kernel used for the optimization
        self.kernel = options["kernel"].copy()
        # Inference method used to approximate the posterior
        self.inference = options["inference"]
        # The acquisition function used to get new points
        self.acquisition = options["acquisition"]
        # Number of observations in a batch
        self.batch_size = options["batch_size"]
        # Maximum number of observations allowed
        self.max_num_observations = options["max_num_observations"]

        # Number of iterations the BO loop is ran can be computed from the max number of observations and batch size
        self.iterations = math.ceil(
            float(self.max_num_observations) / float(self.batch_size))

        # Optional parameters that have defaults
        # Noise std the likelihood uses for observations
        self.noise = options.get("noise", 1e-6)

        # If we use comparative observations from the objective function before starting
        self.use_comparative_observations_in_init = options.get(
            "use_comparative_observations_in_init", False)
        # If we use direct observations from the objective function before starting
        self.use_direct_observations_in_init = options.get(
            "use_direct_observations_in_init", False)
        # Boolean indicating if the locations for the initial draws are chosen at random or selected uniformly from a grid
        self.random = options.get("random", False)

        # Log file used to store all print outputs during the BO
        self.log_file = options.get("log_file", None)

        # Configure logger
        configure_logger(log_file=self.log_file)

    def get_logger(self) -> logging.Logger:
        """
        Get the logging function used to save the print outputs
        :return: a logger where the prints are directed
        """
        return logging.getLogger(self.log_file)

    def bayesian_optimization(self, objective: TestFunction) -> Tuple[np.ndarray, np.ndarray]:
        """
        This function implements the main loop of Bayesian Optimization,

        The function takes the objective

        The function returns the final set of points X_all, the respective
        batch feedbacks yc_all

        :param objective: The black box function to be optimized
        :return: The locations the function has been evaluated so far and the comparison outcomes
        """

        # SET UP THE GP MODEL #
        bounds = objective.bounds
        dim = len(bounds)

        lik = GPy.likelihoods.Gaussian()
        lik.variance.constrain_fixed(self.noise**2, warning=False)
        noise = self.noise

        X0 = np.empty((0, dim))
        y = []
        yc = []

        def objective_modifier(x, f=None, batch_size=1):
            return np.concatenate(
                tuple(
                    f(x[:, i * batch_size: (i + 1) * batch_size]).reshape((-1, 1))
                    for i in range(x.shape[1] // batch_size)
                ),
                axis=1,
            )

        # Initial observations:
        if self.use_comparative_observations_in_init:
            if self.random:
                X0 = random_sample(bounds, 2**dim)
            else:
                X0 = grid_sample(dim)
            yc = give_comparisons(objective.f, X0)
        if self.use_direct_observations_in_init:
            if self.random:
                Xn = random_sample(bounds, 2**dim)
            else:
                Xn = grid_sample(dim)
            yn = objective.f(Xn).reshape((-1, 1))
            y = [(X0.shape[0] + i, yi) for i, yi in enumerate(yn)]
            X0 = np.concatenate((X0, Xn), axis=0)

        if not self.use_comparative_observations_in_init and not self.use_direct_observations_in_init:
            m = self.inference(
                static_sample(bounds),
                [(i, yi) for i, yi in enumerate(np.array([[0], [0]]))],
                yc,
                self.kernel.copy(),
                lik,
                get_logger=self.get_logger,
            )
        else:
            m = self.inference(X0, y, yc, self.kernel.copy(),
                               lik, get_logger=self.get_logger)
        # CREATE BO LOOP #
        bo_loop = create_bayesian_optimization_loop(
            m, bounds, self.batch_size, self.acquisition)

        # RUN THE LOOP #
        bo_loop.run_loop(partial(objective_modifier, f=objective.f,
                         batch_size=self.batch_size), self.iterations)
        return m.X, m.yc

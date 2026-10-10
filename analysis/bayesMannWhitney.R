# The following code is taken from: https://osf.io/gny35/ for
# Bayesian Mann-Whitney Test.

truncNormSample <- function(lBound = -Inf, uBound = Inf, mu = 0, sd = 1) {

  lBoundUni <- pnorm(lBound, mean = mu, sd = sd)
  uBoundUni <- pnorm(uBound, mean = mu, sd = sd)
  mySample <- qnorm(runif(1, lBoundUni, uBoundUni), mean = mu, sd = sd)

  return(mySample)
}

upperLowerTruncation <- function(ranks, values, currentRank) {

  if (currentRank == min(ranks)) {
    under <- -Inf
  } else {
    under <- max(values[ranks < currentRank])
  }

  if (currentRank == max(ranks)) {
    upper <- Inf
  } else {
    upper <- min(values[ranks > currentRank])
  }

  return(list(under=under, upper=upper))
}

rankSumGibbsSampler <- function(xVals, yVals, nSamples = 1e3, cauchyPriorParameter = 1/sqrt(2),  progBar = TRUE,
                                nBurnin = 1, nGibbsIterations = 10, nChains = 10) {

  if (progBar) {
    myBar <- txtProgressBar(min = 1, max = nSamples*nChains, initial = 1, char = "*",style=3,width=50)
  }

  n1 <- length(xVals)
  n2 <- length(yVals)

  allRanks <- rank(c(xVals,yVals))
  xRanks <- allRanks[1:n1]
  yRanks <- allRanks[(n1+1):(n1+n2)]

  deltaSamples <- numeric(nSamples)
  deltaSamplesMatrix <- matrix(ncol = nChains, nrow = nSamples-nBurnin)
  totalIterCount <- 0

  for(thisChain in 1:nChains) {

    currentVals <- sort(rnorm((n1+n2)))[allRanks] # initial values

    oldDeltaProp <- 0

    for (j in 1:nSamples) {

      for (i in sample(1:(n1+n2))) {

        currentRank <- allRanks[i]

        currentBounds <- upperLowerTruncation(ranks=allRanks, values=currentVals, currentRank=currentRank)
        if (i <= n1) {
          oldDeltaProp <- -0.5*oldDeltaProp
        } else {
          oldDeltaProp <- 0.5*oldDeltaProp
        }

        currentVals[i] <- truncNormSample(currentBounds[["under"]], currentBounds[["upper"]], mu=oldDeltaProp, sd=1)

      }

      xVals <- currentVals[1:n1]
      yVals <- currentVals[(n1+1):(n1+n2)]

      gibbsResult <- sampleGibbsTwoSampleWilcoxon(x = xVals, y = yVals, nIter = nGibbsIterations,
                                                  rscale = cauchyPriorParameter)

      deltaSamples[j] <- oldDeltaProp <- gibbsResult
      if (progBar) setTxtProgressBar(myBar, j + ( (thisChain-1) * nSamples))

    }

    if (nBurnin > 0) {
      deltaSamples <- -deltaSamples[-(1:nBurnin)]
    } else {
      deltaSamples <- -deltaSamples
    }

    deltaSamplesMatrix[, thisChain] <- deltaSamples

  }

  betweenChainVar <- (nSamples / (nChains - 1)) * sum((apply(deltaSamplesMatrix, 2, mean)  - mean(deltaSamplesMatrix))^2)
  withinChainVar <- (1/ nChains) * sum(apply(deltaSamplesMatrix, 2, var))

  fullVar <- ((nSamples - 1) / nSamples) * withinChainVar + (betweenChainVar / nSamples)
  rHat <- sqrt(fullVar/withinChainVar)

  return(list(deltaSamples = as.vector(deltaSamplesMatrix), rHat = rHat))
}

sampleGibbsTwoSampleWilcoxon <- function(x, y, nIter = 10, rscale = 1/sqrt(2)) {
  meanx <- mean(x)
  meany <- mean(y)
  n1 <- length(x)
  n2 <- length(y)
  sigmaSq <- 1 # Arbitrary number for sigma
  g <- 1
  for(i in 1:nIter){
    #sample mu
    varMu <- (4 * g * sigmaSq) / ( 4 + g * (n1 + n2) )
    meanMu <- (2 * g * (n2 * meany - n1 * meanx)) / ((g * (n1 + n2) + 4))
    mu <- rnorm(1, meanMu, sqrt(varMu))
    # sample g
    betaG <- (mu^2 + sigmaSq * rscale^2) / (2*sigmaSq)
    g <- 1/rgamma(1, 1, betaG)
    # convert to delta
    delta <- mu / sqrt(sigmaSq)
  }
  return(delta)
}
# this function computes  BF10 for both Wilcoxon tests and Spearman's rho, as specified in whichTest. Recommended values
# for Wilcoxon are 1/sqrt(2) and 1 for Spearman. These should be the same as specified in the Gibbs sampler function call.
# The oneSided argument can be FALSE (for two-sided tests), "right" for positive one-sided tests, and "left" for negative
# one-sided tests.
computeBayesFactorOneZero <- function(posteriorSamples, priorParameter = 1, oneSided = FALSE, whichTest = "Wilcoxon") {

  postDens <- logspline::logspline(posteriorSamples)
  densZeroPoint <- logspline::dlogspline(0, postDens)

  corFactorPosterior <- logspline::plogspline(0, postDens)
  if (oneSided == "right")
    corFactorPosterior <- 1 - corFactorPosterior

  if (whichTest == "Wilcoxon") {
    # priorParameter should be the Cauchy scale parameter
    priorDensZeroPoint <- dcauchy(0, scale = priorParameter)
    corFactorPrior <-  pcauchy(0, scale = priorParameter, lower.tail = (oneSided != "right" ))
  } else if (whichTest == "Spearman") {
    # priorParameter should be kappa
    priorDensZeroPoint <- dbeta(0.5, 1/priorParameter, 1/priorParameter) / 2
    corFactorPrior <-  pbeta(0.5, 1/priorParameter, 1/priorParameter, lower.tail = (oneSided != "right" ))
  }

  if (isFALSE(oneSided)) {
    bf10 <- priorDensZeroPoint / densZeroPoint
  } else {
    bf10 <- (priorDensZeroPoint / corFactorPrior) / (densZeroPoint / corFactorPosterior)
  }

  return(bf10)
}
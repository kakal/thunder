# localcorr <master> <inputFile_X> <outputFile> <neighborhood> <mxX> <mxY>"
#
# correlate the time series of each pixel
# in an image with its local neighborhood
#
# example:
# localcorr.py local data/fish.txt results 5 88 76
#

import argparse
import os
from numpy import corrcoef
from thunder.util.dataio import *
from pyspark import SparkContext


def clip(val, mn, mx):
    if val < mn:
        return mn
    if val > mx:
        return mx
    else:
        return val


def mapToNeighborhood(ind, ts, sz, mxX, mxY):
    # create a list of key value pairs with multiple shifted copies
    # of the time series ts
    rngX = range(-sz, sz+1, 1)
    rngY = range(-sz, sz+1, 1)
    out = list()
    for x in rngX:
        for y in rngY:
            newX = clip(ind[0] + x, 1, mxX)
            newY = clip(ind[1] + y, 1, mxY)
            newind = (newX, newY, ind[2])
            out.append((newind, ts))
    return out


def localcorr(sc, dataFile, outputDir, sz, mxX, mxY):

    if not os.path.exists(outputDir):
        os.makedirs(outputDir)

    # TODO: use top once implemented in psypark to get mxX and mxY

    # parse data
    lines = sc.textFile(dataFile)
    data = parse(lines, "raw", "xyz").cache()

    # flatmap to key value pairs where the key is neighborhood identifier and value is time series
    neighbors = data.flatMap(lambda (k, v): mapToNeighborhood(k, v, sz, mxX, mxY))

    # TODO: printing here seems to fix a hang later, possibly a bug
    print(neighbors.first())

    # reduceByKey to get the average time series for each neighborhood
    means = neighbors.reduceByKey(lambda x, y: x + y).map(lambda (k, v): (k, v / ((2*sz+1)**2)))

    # join with the original time series data to compute correlations
    result = data.join(means)

    # get correlations and keys
    # TODO: use sortByKey once implemented in pyspark so we don't need to save keys
    corr = result.map(lambda (k, v): (k, corrcoef(v[0], v[1])[0, 1])).cache()

    saveout(corr.map(lambda (k, v): k[0]), outputDir, "x", "matlab")
    saveout(corr.map(lambda (k, v): k[1]), outputDir, "y", "matlab")
    saveout(corr.map(lambda (k, v): v), outputDir, "corr", "matlab")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="correlate time series with neighbors")
    parser.add_argument("master", type=str)
    parser.add_argument("dataFile", type=str)
    parser.add_argument("outputDir", type=str)
    parser.add_argument("sz", type=int)
    parser.add_argument("mxX", type=int)
    parser.add_argument("mxY", type=int)

    args = parser.parse_args()
    sc = SparkContext(args.master, "localcorr")

    localcorr(sc, args.dataFile, args.outputDir + "-localcorr", args.sz, args.mxX, args.mxY)
import numpy as np
from rlscore.learner.query_rankrls import QueryRankRLS
from rlscore.measure import cindex
from rlscore.reader import read_sparse
from rlscore.utilities.cross_validation import map_ids

def train_rls():
    #Select regparam with k-fold cross-validation,
    #where instances related to a single sentence form
    #together a fold
    X_train =  read_sparse("data/train_2000_x.txt")
    Y_train =  np.loadtxt("data/train_2000_y.txt")
    X_test =  read_sparse("data/test_2000_x.txt")
    Y_test =  np.loadtxt("data/test_2000_y.txt")
    #list of sentence ids
    qids_train =  np.loadtxt("data/train_2000_qids.txt")
    qids_test = np.loadtxt("data/test_2000_qids.txt")
    learner = QueryRankRLS(X_train, Y_train, qids_train)
    P_test = learner.predict(X_test)
    folds = map_ids(qids_train)
    perfs = []
    for fold in folds:
        if np.var(Y_train[fold]) != 0:
            P = learner.holdout(fold)
            c = cindex(Y_train[fold], P)
            perfs.append(c)
    perf = np.mean(perfs)
    print("leave-query-out cross-validation cindex %f" %perf)
    partition = map_ids(qids_test)
    test_perfs = []
    #compute the ranking accuracy separately for each test query
    for query in partition:
        #skip such queries, where all instances have the same
        #score, since in this case cindex is undefined
        if np.var(Y_test[query]) != 0:
            perf = cindex(Y_test[query], P_test[query])
            test_perfs.append(perf)
    test_perf = np.mean(test_perfs)
    print("test cindex %f" %test_perf)


if __name__=="__main__":
    train_rls()

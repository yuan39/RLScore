import numpy as np
from rlscore.learner.rls import LeaveOneOutRLS
from rlscore.measure import accuracy
from rlscore.reader import read_svmlight
import random
random.seed(10)

def train_rls():
    X_train, Y_train, foo = read_svmlight("a1a.t")
    X_test, Y_test, foo = read_svmlight("a1a")
    #select randomly 500 basis vectors
    indices = range(X_train.shape[0])
    indices = random.sample(indices, 500)
    basis_vectors = X_train[indices]
    regparams = [2.**i for i in range(-15, 16)]
    gammas = regparams
    best_regparam = None
    best_gamma = None
    best_acc = 0.
    best_learner = None
    for gamma in gammas:
        #New RLS is initialized for each kernel parameter
        learner = LeaveOneOutRLS(X_train, Y_train, basis_vectors= basis_vectors, kernel="GaussianKernel", gamma=gamma, regparams=regparams, measure=accuracy)
        acc = np.max(learner.cv_performances)
        if acc > best_acc:
            best_acc = acc
            best_regparam = learner.regparam
            best_gamma = gamma
            best_learner = learner
    P_test = best_learner.predict(X_test)
    print("best parameters gamma %f regparam %f" %(best_gamma, best_regparam))
    print("best leave-one-out accuracy %f" %best_acc)
    print("test set accuracy %f" %accuracy(Y_test, P_test))

if __name__=="__main__":
    train_rls()

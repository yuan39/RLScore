
#import pyximport; pyximport.install()

import cython_mmc
import numpy as np
import random as pyrandom
pyrandom.seed(200)

from rlscore.learner.abstract_learner import AbstractSvdLearner
from rlscore.utilities import array_tools

class SteepestDescentMMC(AbstractSvdLearner):
    
    
    def __init__(self, **kwargs):
        super(SteepestDescentMMC, self).__init__(**kwargs)
        if kwargs.has_key('callback'):
            self.callbackfun = kwargs['callback']
        else:
            self.callbackfun = None
        self.regparam = float(kwargs["regparam"])
        self.constraint = 0
        if not kwargs.has_key('number_of_clusters'):
            raise Exception("Parameter 'number_of_clusters' must be given.")
        self.labelcount = int(kwargs['number_of_clusters'])
         
        if self.labelcount == 2:
            self.oneclass = True
        else:
            self.oneclass = False
        
        if kwargs.has_key("train_labels"):
            train_labels = kwargs["train_labels"]
        else:
            train_labels = None
        if train_labels != None:
            #Y_orig = array_tools.as_labelmatrix(train_labels)
            Y_orig = array_tools.as_array(train_labels)
            #if Y_orig.shape[1] == 1:
            if len(Y_orig.shape) == 1:
                self.Y = np.zeros((Y_orig.shape[0], 2))
                self.Y[:, 0] = Y_orig
                self.Y[:, 1] = - Y_orig
                self.oneclass = True
            else:
                self.Y = Y_orig.copy()
                self.oneclass = False
            for i in range(self.Y.shape[0]):
                largestind = 0
                largestval = self.Y[i, 0]
                for j in range(self.Y.shape[1]):
                    if self.Y[i, j] > largestval:
                        largestind = j
                        largestval = self.Y[i, j]
                    self.Y[i, j] = -1.
                self.Y[i, largestind] = 1.
        else:
            size = self.svecs.shape[0]
            ysize = self.labelcount
            if self.labelcount == None: self.labelcount = 2
            self.Y = RandomLabelSource(size, ysize).readLabels()
        self.size = self.Y.shape[0]
        self.labelcount = self.Y.shape[1]
        self.classvec = - np.ones((self.size), dtype = np.int32)
        self.classcounts = np.zeros((self.labelcount), dtype = np.int32)
        for i in range(self.size):
            clazzind = 0
            largestlabel = self.Y[i, 0]
            for j in range(self.labelcount):
                if self.Y[i, j] > largestlabel:
                    largestlabel = self.Y[i, j]
                    clazzind = j
            self.classvec[i] = clazzind
            self.classcounts[clazzind] = self.classcounts[clazzind] + 1
        
        self.svecs_list = []
        for i in range(self.size):
            self.svecs_list.append(self.svecs[i].T)
        self.fixedindices = []
        if kwargs.has_key("fixed_indices"):
            self.fixedindices = kwargs["fixed_indices"]
        else:
            self.fixedindices = []
        self.results = {}
    
    
    def createLearner(cls, **kwargs):
        learner = cls(**kwargs)
        return learner
    createLearner = classmethod(createLearner)
    
    
    def train(self):
        self.solve(self.regparam)
       
    
    
    def solve(self, regparam):
        self.regparam = regparam
        
        #Cached results
        self.evals = np.multiply(self.svals, self.svals)
        self.newevals = 1. / (self.evals + self.regparam)
        newevalslamtilde = np.multiply(self.evals, self.newevals)
        self.D = np.sqrt(newevalslamtilde)
        #self.D = -newevalslamtilde
        
        self.VTY = self.svecs.T * self.Y
        #DVTY = np.multiply(self.D.T, self.svecs.T * self.Y)
        
        #self.R = self.svecs * np.multiply(newevalslamtilde.T, self.svecs.T)
        
        self.sqrtR = np.multiply(np.sqrt(newevalslamtilde), self.svecs)
        self.R = self.sqrtR * self.sqrtR.T
        self.mdiagRx2 = - 2 * np.diag(self.R)
        
        '''
        #Space efficient variation
        self.R = None
        self.mdiagRx2 = - 2 * array(sum(np.multiply(self.sqrtR, self.sqrtR), axis = 1)).reshape((self.size))
        '''
        
        self.RY = self.sqrtR * (self.sqrtR.T * self.Y)
        self.Y_Schur_RY = np.multiply(self.Y, self.RY)
        
        #Using lists in order to avoid unnecessary matrix slicings
        #self.DVTY_list = []
        #self.YTVDDVTY_list = []
        self.YTRY_list = []
        self.classFitnessList = []
        for i in range(self.labelcount):
            #DVTY_i = DVTY[:,i]
            #self.DVTY_list.append(DVTY_i)
            YTRY_i = self.Y[:,i].T * self.RY[:,i]
            self.YTRY_list.append(YTRY_i)
            fitness_i = self.size - YTRY_i
            self.classFitnessList.append(fitness_i[0, 0])
        self.classFitnessRowVec = np.array(self.classFitnessList)
        
        self.updateA()
        
        
        converged = False
        #print self.classcounts.T
        if not self.callbackfun == None:
            self.callbackfun.callback(self)
        '''while True:
            
            converged = self.findSteepestDir()
            print self.classcounts.T
            self.callback()
            if converged: break
        
        '''
        
        cons = self.size / self.labelcount
        #self.focusset = self.findNewFocusSet()
        for i in range(20):
            #self.focusset = self.findNewFocusSet()
            #self.focusset = pyrandom.sample(range(self.size),50)
            #print self.focusset
            #cons = len(self.focusset) / self.labelcount
            #converged = self.findSteepestDirRotateClasses(cons / (2. ** i))
            converged = self.findSteepestDirRotateClasses(cons / (2. ** i))
            #converged = self.findSteepestDirRotateClasses(1000)
            #print self.classcounts.T
            self.callback()
            if converged: break
        
        if self.oneclass:
            self.Y = self.Y[:, 0]
        self.results = {}
        self.results['predicted_clusters_for_training_data'] = self.Y
    
    
    def computeGlobalFitness(self):
        fitness = 0.
        for classind in range(self.labelcount):
            fitness += self.classFitnessList[classind]
        return fitness
    
    
    def updateA(self):
        self.A = self.svecs * np.multiply(self.newevals.T, self.VTY)
    
    
    def findSteepestDirRotateClasses(self, howmany, LOO = False):
        #print self.Y.shape,self.R.shape, self.RY.shape, self.Y_Schur_RY.shape, self.classFitnessRowVec.shape, self.mdiagRx2.shape, self.classcounts.shape, self.classvec.shape
        cython_mmc.findSteepestDirRotateClasses(self.Y,
                                                self.R,
                                                self.RY,
                                                self.Y_Schur_RY,
                                                self.classFitnessRowVec,
                                                self.mdiagRx2,
                                                self.classcounts,
                                                self.classvec,
                                                self.size,
                                                self.labelcount,
                                                howmany,
                                                self.sqrtR,
                                                self.sqrtR.shape[1])
        return
        
        #The slow python code. Use the above cython instead.
        for newclazz in range(self.labelcount):
            
            #!!!!!!!!!!!!!!!
            takenum = (self.size / self.labelcount) - self.classcounts[newclazz] + int(howmany)
            
            for h in range(takenum):
                dirsneg = self.classFitnessRowVec + (2 * self.mdiagRx2[:, None] + 4 * np.multiply(self.Y, self.RY))
                dirsnegdiff = dirsneg - self.classFitnessRowVec
                dirscc = dirsnegdiff[np.arange(self.size), self.classvec].T
                dirs = dirsnegdiff + dirscc
                dirs[np.arange(self.size), self.classvec] = float('Inf')
                dirs = dirs[:, newclazz]
                steepestdir = np.argmin(dirs)
                steepness = np.amin(dirs)
                oldclazz = self.classvec[steepestdir]
                self.Y[steepestdir, oldclazz] = -1.
                self.Y[steepestdir, newclazz] = 1.
                self.classvec[steepestdir] = newclazz
                self.classcounts[oldclazz] = self.classcounts[oldclazz] - 1
                self.classcounts[newclazz] = self.classcounts[newclazz] + 1
                self.RY[:, oldclazz] = self.RY[:, oldclazz] - 2 * self.R[:, steepestdir]
                self.RY[:, newclazz] = self.RY[:, newclazz] + 2 * self.R[:, steepestdir]
                
                for i in range(self.labelcount):
                    YTRY_i = self.Y[:,i].T * self.RY[:,i]
                    fitness_i = self.size - YTRY_i
                    self.classFitnessRowVec[i] = fitness_i[0, 0]
                
                self.updateA()
            #self.callback()
        return False
    
    
    def findSteepestDirRotateClasses_FOCUSSETSTUFF(self, howmany, LOO = False):
        
        focusrange = np.mat(np.arange(self.size)).T
        
        for j in range(self.labelcount):
            #maxtake = self.size / self.labelcount
            #maxtake = int(np.sqrt(self.size))
            #!!!!!!!!!!!!!!!
            takenum = (self.size / self.labelcount) - self.classcounts[j] + int(howmany)
            #takenum = min([maxtake, (self.size / self.labelcount) - self.classcounts[j] + int(howmany)])
            #self.focusset = self.findNewFocusSet(j)
            #self.focusset = pyrandom.sample(range(self.size),50)
            #takenum = 2*((len(self.focusset) / self.labelcount) - (len(self.focusset) / self.size) * self.classcounts[j] + int(howmany))
            #print takenum
            #self.focusset = pyrandom.sample(range(self.size),takenum[0,0])
            #self.focusset = self.findNewFocusSet(j, maxtake)
            #self.focusset = set(range(self.size))
            for h in range(takenum):
                self.focusset = set(pyrandom.sample(range(self.size),10))
                dirsnegdiff = 2 * self.mdiagRx2 + 4 * np.multiply(self.Y, self.RY)
                dirscc = dirsnegdiff[focusrange, self.classvec]
                dirs = dirsnegdiff + dirscc
                dirs[focusrange, self.classvec] = float('Inf')
                dirs[list(set(range(self.size))-self.focusset)] = float('Inf')
                dirs = dirs[:, j]
                steepestdir, newclazz = np.unravel_index(np.argmin(dirs), dirs.shape)
                newclazz = j
                oldclazz = self.classvec[steepestdir, 0]
                
                self.Y[steepestdir, oldclazz] = -1.
                self.Y[steepestdir, newclazz] = 1.
                self.classvec[steepestdir] = newclazz
                self.classcounts[oldclazz] = self.classcounts[oldclazz] - 1
                self.classcounts[newclazz] = self.classcounts[newclazz] + 1
                self.RY[:, oldclazz] = self.RY[:, oldclazz] - 2 * self.R[steepestdir].T
                self.RY[:, newclazz] = self.RY[:, newclazz] + 2 * self.R[steepestdir].T
            '''
            while True:
                if takecount >= takenum: break
                for h in range(maxtake):
                    diagR = mat(diag(self.R)).T
                    dirsnegdiff = - 4 * diagR + 4 * np.multiply(self.Y, self.RY)
                    dirscc = dirsnegdiff[focusrange, self.classvec]
                    dirs = dirsnegdiff + dirscc
                    dirs[focusrange, self.classvec] = float('Inf')
                    dirs[list(set(range(self.size))-self.focusset)] = float('Inf')
                    dirs = dirs[:, j]
                    steepestdir, newclazz = unravel_index(argmin(dirs), dirs.shape)
                    newclazz = j
                    oldclazz = self.classvec[steepestdir, 0]
                    
                    self.Y[steepestdir, oldclazz] = -1.
                    self.Y[steepestdir, newclazz] = 1.
                    self.classvec[steepestdir] = newclazz
                    self.classcounts[oldclazz] = self.classcounts[oldclazz] - 1
                    self.classcounts[newclazz] = self.classcounts[newclazz] + 1
                    self.RY[:, oldclazz] = self.RY[:, oldclazz] - 2 * self.R[steepestdir].T
                    self.RY[:, newclazz] = self.RY[:, newclazz] + 2 * self.R[steepestdir].T
                    takecount += 1
                    if takecount >= takenum: break
                if takecount >= takenum: break
                self.focusset = self.findNewFocusSet(j, maxtake)
                '''
            self.callback()
        return False
    
    
    def findNewFocusSet(self, clazz = 0, focsize = 50):
        
        diagR = np.mat(np.diag(self.R)).T
        dirsnegdiff = - 4 * diagR + 4 * np.multiply(self.Y, self.RY)
        dirscc = dirsnegdiff[np.mat(np.arange(self.size)).T, self.classvec]
        dirs = dirsnegdiff + dirscc
        dirs[np.mat(np.arange(self.size)).T, self.classvec] = float('Inf')
        
        dirlist = []
        for i in range(self.size):
            row = dirs[i]
            #dirlist.append((amin(row), i))
            dirlist.append((row[0, clazz], i))
            dirlist = sorted(dirlist)[0:focsize]
        focusset = []
        for i in range(focsize):
            focusset.append(dirlist[i][1])
        return set(focusset)
        





class RandomLabelSource(object):
    
    def __init__(self, size, labelcount):
        self.rand = pyrandom.Random()
        self.rand.seed(100)
        self.Y = - np.ones((size, labelcount), dtype = np.float64)
        self.classvec = - np.ones((size), dtype = np.int32)
        allinds = set(range(size))
        self.classcounts = np.zeros((labelcount), dtype = np.int32)
        for i in range(labelcount-1):
            inds = self.rand.sample(allinds, size / labelcount) #sampling without replacement
            allinds = allinds - set(inds)
            for ind in inds:
                self.Y[ind, i] = 1.
                self.classvec[ind] = i
                self.classcounts[i] += 1
        for ind in allinds:
            self.Y[ind, labelcount - 1] = 1.
            self.classvec[ind] = labelcount - 1
            self.classcounts[labelcount - 1] += 1
    
    def readLabels(self):
        return self.Y


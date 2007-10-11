
from baseObjects import PreParser
from document import StringDocument
from c3errors import ConfigFileException

import os, random, cPickle, tempfile
import numarray as na

import svm
from reverend import thomas
from bpnn import NN

class VectorRenumberPreParser(PreParser):

    _possibleSettings = {'termOffset' : {'docs' : "", 'type' : int}} 
    _possiblePaths = {'modelPath' : {'docs' : ""}}

    def __init__(self, session, config, parent):
        PreParser.__init__(self, session, config, parent)
        # Some settings that are needed at this stage
        self.offset = self.get_setting(session, 'termOffset', 0)
        
    def process_document(self, session, doc):
        (labels, vectors) = doc.get_raw()

        # find max attr
        all = {}
        for v in vectors:
            all.update(v)
        keys = all.keys()
        keys.sort()
        maxattr = keys[-1]
        nattrs = len(keys)

        # remap vectors to reduced space
        renumbers = range(self.offset, nattrs+self.offset)
        renumberhash = dict(zip(keys, renumbers))
        newvectors = []
        for vec in vectors:
            new = {}
            for (k,v) in vec.items():
                new[renumberhash[k]] = v 
            newvectors.append(new)

        # pickle renumberhash
        pick = cPickle.dumps(renumberhash)
        filename = self.get_path(session, 'modelPath', None)
        if not filename:
            dfp = self.get_path(session, 'defaultPath')
            filename = os.path.join(dfp, self.id + "_ATTRHASH.pickle")
        f = file(filename, 'w')
        f.write(pick)
        f.close()

        return StringDocument((labels, newvectors, nattrs))

class VectorUnRenumberPreParser(PreParser):

    _possibleSettings = {'termOffset' : {'docs' : "", 'type' : int}} 
    _possiblePaths = {'modelPath' : {'docs' : ""}}

    def __init__(self, session, config, parent):
        PreParser.__init__(self, session, config, parent)
        # Some settings that are needed at this stage
        self.offset = self.get_setting(session, 'termOffset', 0)
        filename = self.get_path(session, 'modelPath', None)
        if not filename:
            dfp = self.get_path(session, 'defaultPath')
            filename = os.path.join(dfp, self.id + "_ATTRHASH.pickle")
        self.modelPath = filename
        self.model = {}
        self.lastModTime = 0
        self.load_model(session)

    def load_model(self, session):
        # Store last written time, in case we change
        filename = self.modelPath
        if os.path.exists(filename):
            si = os.stat(filename)
            lastMod = si.st_mtime
            if lastMod > self.lastModTime:
                inh = file(filename)
                inhash = cPickle.load(inh)
                inh.close()
                # now reverse our keys/values
                self.model = dict(zip(inhash.values(), inhash.keys()))

                si = os.stat(filename)
                self.lastModTime = si.st_mtime

                return 1
            else:
                return 0
        else:
            return 0


    def process_document(self, session, doc):
        self.load_model(session)
        data = doc.get_raw()
        # data should be list of list of ints to map
        g = self.model.get
        ndata = []
        for d in data:
            n = []
            for i in d:
                n.append(g(i))
            ndata.append(n)
        return StringDocument(ndata)
    

class ARMVectorPreParser(PreParser):
    # no classes

    def process_document(self, session, doc):
        (labels, vectors) = doc.get_raw()[:2]
        txt = []
        for v in vectors:
            k = v.keys()
            if k:
                k.sort()
                txt.append(' '.join(map(str, k)))
        return StringDocument('\n'.join(txt))


class ARMPreParser(PreParser):

    _possibleSettings = {'support' : {'docs' : "Support value", 'type' : int},
                         'confidence' : {'docs' : "Confidence value", 'type' : int},
                         } 


    def __init__(self, session, config, parent):
        PreParser.__init__(self, session, config, parent)
        self.support = self.get_setting(session, 'support', 10)
        self.confidence = self.get_setting(session, 'confidence', 75)

class TFPPreParser(ARMPreParser):

    _possibleSettings = {'memory' : {'docs' : "How much memory to let Java use", 'type' : int}
                         } 
    _possiblePaths = {'filePath' : {'docs' : 'Directory where TFP lives'},
                      'javaPath' : {'docs' : 'Full path to java executable'}
                      }

    def __init__(self, session, config, parent):
        ARMPreParser.__init__(self, session, config, parent)

        # Check we know where TFP is etc
        self.filePath = self.get_setting(session, 'filePath', None)
        if not self.filePath:
            raise ConfigFileException("%s requires the path: filePath" % self.id)
        self.java = self.get_path(session, 'javaPath', 'java')
        self.memory = self.get_setting(session, 'memory', 1000)

    def process_document(self, session, doc):

        # write out our temp file
        (qq, infn) = tempfile.mkstemp(".tfp")
        fh = file(infn, 'w')
        fh.write(doc.get_raw())
        fh.close()

        # go to TFP directory and run
        o = os.getcwd()
        os.chdir(self.filePath)
        results = commands.getoutput("%s -Xms%sm -Xmx%sm AprioriTFPapp -F../%s -S%s -C%s" % (self.java, self.memory, self.memory, infn, self.support, self.confidence))
        os.chdir(o)

        # process results
        resultLines = results.split('\n')
        matches = []
        for l in resultLines:
            m = freqRe.search(l)
            if m:
                (set, freq) = m.groups()
                matches.append((int(freq), set))
                
        if not matches:
            # no FIS for some reason, return results??
            return StringDocument(results)
        matches.sort(reverse=True)
        return StringDocument(matches)


class ClassificationPreParser(PreParser):
    """ Parent for all C12n PreParsers """

    model = None
    predicting = 0

    _possiblePaths = {'modelPath' : {'docs' : "Path to where the model is (to be) stored"}}
    _possibleSettings = {'termOffset' : {'docs' : "", 'type' : int}}

    def __init__(self, session, config, parent):
        PreParser.__init__(self, session, config, parent)
        self.offset = self.get_setting(session, 'termOffset', 0)
        modelPath = self.get_path(session, 'modelPath', '')
        if not modelPath:
            raise ConfigFileException("Classification PreParser (%s) does not have a modelPath" % self.id)
        if (not os.path.isabs(modelPath)):
            dfp = self.get_path(session, 'defaultPath')
            modelPath = os.path.join(dfp, modelPath)
            self.paths['modelPath'] = modelPath
        if os.path.exists(modelPath):
            # load model
            self.load_model(session, modelPath)
        else:
            self.model = None

        self.renumber = {}
        
            
    def process_document(self, session, doc):
        if self.model != None and self.predicting:
            # predict
            return self.predict(session, doc)
        else:
            # train
            return self.train(session, doc)

    def load_model(self, session, path):
        # should set self.model to not None
        raise NotImplementedError

    def train(self, session, doc):
        # should set self.model to new model, return doc
        raise NotImplementedError

    def predict(self, session, doc):
        # use self.model to predict class and return annotated doc
        raise NotImplementedError

    def renumber_train(self, session, vectors):
        # find max attr
        all = {}
        for v in vectors:
            all.update(v)
        keys = all.keys()
        keys.sort()
        maxattr = keys[-1]
        nattrs = len(keys)

        if nattrs < (maxattr / 2):
            # remap vectors to reduced space
            renumbers = range(self.offset, nattrs+self.offset)
            renumberhash = dict(zip(keys, renumbers))
            newvectors = []
            for vec in vectors:
                new = {}
                for (k,v) in vec.items():
                    new[renumberhash[k]] = v
                newvectors.append(new)
            # need this to map for future docs!
            self.renumber = renumberhash
        else:
            newvectors = vectors

        # pickle renumberhash
        pick = cPickle.dumps(renumberhash)
        f = file(self.get_path(session, 'modelPath') + "_ATTRHASH.pickle", 'w')
        f.write(pick)
        f.close()
        return (nattrs, newvectors)

    def renumber_test(self, vector):
        if self.renumber:
            new = {}
            for (a,b) in vector.items():
                try:
                    new[self.renumber[a]] = b
                except:
                    # token not present in training, ignore
                    pass
            return new
        else:
            return vector


class LibSVMPreParser(ClassificationPreParser):

    _possibleSettings = {'c-param' : {'docs' : "Parameter for SVM", 'type' : int},
                         'gamma-param' : {'docs' : "Parameter for SVM", 'type' : float},
                         'degree-param' : {'docs' : "Parameter for SVM", 'type' : int},
                         'cache_size-param' : {'docs' : "Parameter for SVM", 'type' : int},
                         'shrinking-param' : {'docs' : "Parameter for SVM", 'type' : int},
                         'probability-param' : {'docs' : "Parameter for SVM", 'type' : int},
                         'nu-param' : {'docs' : "Parameter for SVM", 'type' : float},
                         'p-param' : {'docs' : "Parameter for SVM", 'type' : float},
                         'eps-param' : {'docs' : "Parameter for SVM", 'type' : float},
                         'svm_type-param' : {'docs' : "Parameter for SVM"},
                         'kernel_type-param' : {'docs' : "Parameter for SVM"}
                         }

    def __init__(self, session, config, parent):
        ClassificationPreParser.__init__(self, session, config, parent)
        c = self.get_setting(session, 'c-param', 32)
        g = self.get_setting(session, 'gamma-param', 0.00022)
        # XXX check for other params
        self.param = svm.svm_parameter(C=c,gamma=g)

    def _verifySetting(self, type, value):
        # svm_type, kernel_type, degree, gamma, coef0, nu, cache_size,
        # C, eps, p, shrinking, nr_weight, weight_label, and weight.

        if type in ('svm_type-param', 'kernel_type-param'):
            name = value.toupper()
            if hasattr(svm, name):
                return getattr(svm, name)
            else:
                raise ConfigFileException("No such %s '%s' for object %s" % (type, value, self.id))
        else:
            return ClassificationPreParser._verifySetting(self, type, value)


    def load_model(self, session, path):
        try:
            self.model = svm.svm_model(path.encode('utf-8'))
            self.predicting = 1
        except:
            raise ConfigFileException(path)

    def train(self, session, doc):
        # doc here is [[class,...], [{vector},...]]
        (labels, vectors) = doc.get_raw()
        problem = svm.svm_problem(labels, vectors)
        self.model = svm.svm_model(problem, self.param)
        modelPath = self.get_path(session, 'modelPath')
        self.model.save(str(modelPath))
        self.predicting = 1

    def predict(self, session, doc):
        # doc here is {vector}
        vector = doc.get_raw()
        doc.predicted_class = int(self.model.predict(vector))
        return doc



class ReverendPreParser(ClassificationPreParser):

    def __init__(self, session, config, parent):
        ClassificationPreParser.__init__(self, session, config, parent)
        # create empty model
        self.model = thomas.Bayes()

    def load_model(self, session, path):
        try:
            self.model.load(str(path))
            self.predicting = 1
        except:
            raise ConfigFileException(path)

    def train(self, session, doc):
        (labels, vectors) = doc.get_raw()
        for (l, v) in zip(labels, vectors):
            vstr = ' '.join(map(str, v.keys()))
            self.model.train(l, vstr)
        self.model.save(str(self.get_setting(session, 'modelPath')))
        self.predicting = 1

    def predict(self, session, doc):
        v = ' '.join(map(str, doc.get_raw().keys()))
        probs = bayes.guess(v)
        doc.predicted_class = probs[0][0]
        doc.probabilities = probs
        return doc


class BpnnPreParser(ClassificationPreParser):

    _possibleSettings = {'iterations' : {'docs' : "Number of iterations", 'type' : int},
                         'hidden-nodes' : {'docs' : "Number of hidden nodes", 'type' : int},
                         'learning-param' : {'docs' : "NN param", 'type' : float},
                         'momentum-param' : {'docs' : "NN param", 'type' : float} }

    def __init__(self, session, config, parent):
        ClassificationPreParser.__init__(self, session, config, parent)
        # now get bpnn variables
        self.iterations = int(self.get_setting(session, 'iterations', 500))
        self.hidden = int(self.get_setting(session, 'hidden-nodes', 5))
        self.learning = float(self.get_setting(session, 'learning-param', 0.5))
        self.momentum = float(self.get_setting(session, 'momentum-param', 0.1))
        
    def load_model(self, session, path):
        # load from pickled NN
        self.model = cPickle.load(path)

    def train(self, session, doc):
        # modified bpnn to accept dict as sparse input
        (labels, vectors) = doc.get_raw()
        (nattrs, vectors) = self.renumber_train(session, vectors)

        labelSet = set(labels)
        lls = len(labelSet)
        if lls == 2:
            patts = [(vectors[x], [labels[x]]) for x in xrange(len(labels))]
            noutput = 1
        else:
            if lls < 5:
                templ = ((0, 0), (1,0), (0, 1), (1, 1))
            elif lls < 9:
                templ = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0),
                         (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1))
            else:
                # hopefully not more than 16 classes!
                templ = ((0,0,0,0), (1,0,0,0), (0,1,0,0), (1,1,0,0),
                         (0,0,1,0), (1,0,1,0), (0,1,1,0), (1,1,1,0),
                         (0,0,0,1), (1,0,0,1), (0,1,0,1), (1,1,0,1),
                         (0,0,1,1), (1,0,1,1), (0,1,1,1), (1,1,1,1))
            rll = range(len(labels))
            patts = [(vectors[x], templ[labels[x]]) for x in rll]
            noutput = len(templ[0])
            
        # shuffle to ensure not all of class together
        r = random.Random()
        r.shuffle(patts)

        # only way this is at all usable is with small datasets run in psyco
        # but is at least fun to play with...

        if maxattr * len(labels) > 2000000:
            print "Training NN is going to take a LONG time..."
            print "Make sure you have psyco enabled..."

        n = NN(maxattr, self.hidden, noutput)
        self.model = n
        n.train(patts, self.iterations, self.learning, self.momentum)

        modStr = cPickle.dumps(n)
        f = file(mp, 'w')
        f.write(modStr)
        f.close()
        self.predicting = 1

    def predict(self, session, doc):
        invec = doc.get_raw()
        vec = self.renumber_test(invec)
        resp = self.model.update(vec)
        # this is the outputs from each output node
        print resp


class PerceptronPreParser(ClassificationPreParser):
    # quick implementation of perceptron using numarray

    def load_model(self, session, path):
        self.model = na.fromfile(path)

    def train(self, session, doc):
        # modified bpnn to accept dict as sparse input
        (labels, vectors) = doc.get_raw()
        (nattrs, vectors) = self.renumber_train(session, vectors)

        labelSet = set(labels)
        lls = len(labelSet)
        if lls != 2:
            raise ValueError("Perceptron can only do two classes")
        else:
            patts = [(vectors[x], [labels[x]]) for x in xrange(len(labels))]
        r = random.Random()

        # assume that dataset is too large to fit in memory non-sparse
        # numarray makes this very easy... and *fast*

        weights = na.zeros(nattrs+1)
        iterations = 100
        it = 0
        for i in xrange(iterations):
            it += 1
            r.shuffle(patts)
            wrong = 0
            for (vec, cls) in patts:
                va = na.zeros(nattrs+1)
                for (a,b) in vec.items():
                    va[a] = b
                va[-1] = 1 # bias
                bits = weights * va
                total = bits.sum()
                cls = cls[0]
                if total >= 0 and cls == 0:
                    weights = weights - va
                    wrong = 1
                elif total < 0 and cls == 1:
                    weights = weights + va
                    wrong = 1
            if not wrong:
                # reached perfection
                break
        self.model = weights
        # save model
        weights.tofile(self.get_path(session, 'modelPath'))
        self.predicting = 1

    def predict(self, session, doc):
        invec = doc.get_raw()
        vec = self.renumber_test(invec)
        va = na.zeros(len(self.model))
        for (a,b) in vec.items():
            va[a] = b
        va[-1] = 1 # bias
        bits = self.model * va
        total = bits.sum()

        pred = int(total >= 0)
        doc.predicted_class = pred
        return doc


class CarmPreParser(ClassificationPreParser):
    # Call Frans's code and read back results
    pass


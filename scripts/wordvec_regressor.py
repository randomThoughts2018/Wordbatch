from __future__ import with_statement
from __future__ import division
from __future__ import absolute_import
from __future__ import print_function
import os
import re
import json
import gzip
import wordbatch
from wordbatch.models import FTRL
from wordbatch.extractors import WordVec, Hstack
import threading
import sys
if sys.version_info.major == 3:
    import pickle as pkl
else:
    import cPickle as pkl

non_alphanums = re.compile('[\W+]')
nums_re= re.compile("\W*[0-9]+\W*")
trash_re= [re.compile("<[^>]*>"), re.compile("[^a-z0-9' -]+"), re.compile(" [.0-9'-]+ "), re.compile("[-']{2,}"),
           re.compile(" '"),re.compile("  +")]

def normalize_text(text):
    text= text.lower()
    text= nums_re.sub(" NUM ", text)
    text= " ".join([word for word in non_alphanums.sub(" ",text).strip().split() if len(word)>1])
    return text

class WordvecRegressor(object):
    def __init__(self, pickle_model="", datadir=None):
        self.wb= wordbatch.WordBatch(normalize_text,
                                            extractor=(Hstack,
                                   [(WordVec, {"wordvec_file": "../../../data/word2vec/glove.twitter.27B.100d.txt.gz",
                                    "normalize_text": normalize_text, "encoding": "ISO-8859-1"}),
                                   (WordVec, {"wordvec_file": "../../../data/word2vec/glove.6B.50d.txt.gz",
                                 "normalize_text": normalize_text, "encoding": "ISO-8859-1"})]))

        self.wb.dictionary_freeze= True

        self.clf= FTRL(alpha=1.0, beta=1.0, L1=0.00001, L2=1.0, D=2 ** 25, iters=1, inv_link= "identity")

        if datadir==None:  (self.wb, self.clf)= pkl.load(gzip.open(pickle_model, 'rb'))
        else: self.train(datadir, pickle_model)

    def fit_batch(self, texts, labels, rcount):
        texts, labels = self.wb.shuffle_batch(texts, labels, rcount)
        print("Transforming", rcount)
        texts= self.wb.fit_transform(texts, reset= False)
        print("Training", rcount)
        self.clf.fit(texts, labels, reset= False)

    def train(self, datadir, pickle_model=""):
        texts= []
        labels= []
        training_data= os.listdir(datadir)
        rcount= 0
        batchsize= 100000

        p= None
        for jsonfile in training_data:
            with open(datadir + "/" + jsonfile, 'r') as inputfile:
                for line in inputfile:
                    #if rcount > 1000000: break
                    try: line= json.loads(line.strip())
                    except:  continue
                    for review in line["Reviews"]:
                        rcount+= 1
                        if rcount % 100000 == 0:  print(rcount)
                        if rcount % 6 != 0: continue
                        if "Overall" not in review["Ratings"]: continue
                        texts.append(review["Content"])
                        labels.append((float(review["Ratings"]["Overall"]) - 3) *0.5)
                        if len(texts) % batchsize == 0:
                            if p != None:  p.join()
                            p= threading.Thread(target=self.fit_batch, args=(texts, labels, rcount))
                            p.start()
                            texts= []
                            labels= []
        if p != None:  p.join()
        self.fit_batch(texts, labels, rcount)

        if pickle_model!="":
            with gzip.open(pickle_model, 'wb') as model_file:
                pkl.dump((self.wb, self.clf), model_file, protocol=2)

    def predict(self, texts):
        vecs= self.wb.transform(texts)
        return self.clf.predict(vecs)
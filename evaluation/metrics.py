import numpy as np
from tqdm import tqdm
import scipy.sparse as sparse

def sub_routine(vector_u, matrix_V, vector_train, vector_true, k=500):
    #import ipdb;ipdb.set_trace()
    train_index = vector_train.nonzero()[1]
    vector_predict = matrix_V.dot(vector_u).argsort()[-(k+len(train_index)):][::-1]
    vector_predict = np.delete(vector_predict, np.isin(vector_predict, train_index).nonzero()[0])
    vector_true_dense = vector_true.nonzero()[1]
    return vector_predict[:k], vector_true_dense, np.isin(vector_predict[:k], vector_true_dense)


def r_precision(vector_true_dense, hits, **unused):
    hits = len(hits.nonzero()[0])
    return float(hits)/len(vector_true_dense)


def _dcg_support(size):
    arr = np.arange(1, size+1)+1
    return 1./np.log2(arr)


def ndcg(vector_true_dense, vector_predict, hits):
    idcg = np.sum(_dcg_support(len(vector_true_dense)))
    dcg_base = _dcg_support(len(vector_predict))
    dcg_base[np.logical_not(hits)] = 0
    dcg = np.sum(dcg_base)
    return dcg/idcg


def click(hits, **unused):
    first_hit = next((i for i, x in enumerate(hits) if x), None)
    if first_hit is None:
        first_hit = 5
    return first_hit/10



def evaluate(matrix_U, matrix_V, matrix_Train, matrix_Test, k, metric_names):

    metrics = {
        "R-Precision": r_precision,
        "NDCG": ndcg,
        "Clicks": click
    }

    results = {name: [] for name in metric_names}
    for user_index in tqdm(range(matrix_U.shape[0])):
        vector_u = matrix_U[user_index]
        vector_train = matrix_Train[user_index]
        vector_true = matrix_Test[user_index]
        vector_predict, vector_true_dense, hits = sub_routine(vector_u,
                                                              matrix_V,
                                                              vector_train,
                                                              vector_true,
                                                              k=k)
        for name in metric_names:
            results[name] = metrics[name](vector_true_dense=vector_true_dense,
                                          vector_predict=vector_predict,
                                          hits=hits)

    output = dict()
    for name in metric_names:
        output[name] = np.average(results[name])

    return output




# Test Code
# vector_u = np.random.rand(10)
# matrix_V = sparse.rand(5000, 10).tocsr()
# vector_train = sparse.rand(1, 1000).tocsr()
# vector_true = sparse.rand(1, 1000).tocsr()
#
#
# vector_predict, vector_true_dense, hits = sub_routine(vector_u, matrix_V, vector_train, vector_true, k=500)
# print r_precision(vector_true_dense=vector_true_dense, hits=hits)
# print ndcg(vector_true_dense=vector_true_dense, vector_predict=vector_predict, hits=hits)
# print click(hits=hits)
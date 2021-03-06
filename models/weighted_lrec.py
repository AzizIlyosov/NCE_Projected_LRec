import numpy as np
import scipy
import scipy.sparse as sparse
from scipy.sparse import vstack, hstack
from scipy.linalg import inv as cpu_inv
from sklearn.utils.extmath import randomized_svd
from utils.progress import WorkSplitter, inhour
from tqdm import tqdm
import time


def per_item_gpu(vector_r, matrix_A, matrix_B, matrix_BT, alpha):
    import cupy as cp
    from cupy.linalg import inv as gpu_inv
    vector_r_index = vector_r.nonzero()[0]
    vector_r_small = cp.array(vector_r.data)
    vector_c_small = alpha * vector_r_small
    matrix_B_small = cp.take(matrix_B, vector_r_index, axis=0)
    matrix_BT_small = cp.take(matrix_BT, vector_r_index, axis=1)
    denominator = gpu_inv(matrix_A+(matrix_BT_small*vector_c_small).dot(matrix_B_small))
    return (denominator.dot(matrix_BT_small)).dot((vector_c_small*vector_r_small+vector_r_small)).flatten()


def per_item_cpu(vector_r, matrix_A, matrix_B, matrix_BT, alpha):
    vector_r_index = vector_r.nonzero()[0]
    vector_r_small = vector_r.data
    vector_c_small = alpha * vector_r_small
    matrix_B_small = np.take(matrix_B, vector_r_index, axis=0)
    matrix_BT_small = np.take(matrix_BT, vector_r_index, axis=1)
    denominator = cpu_inv(matrix_A+(matrix_BT_small*vector_c_small).dot(matrix_B_small))
    return (denominator.dot(matrix_BT_small)).dot((vector_c_small*vector_r_small+vector_r_small).T).flatten()


def weighted_lrec_items(matrix_train,
                        embeded_matrix=np.empty((0)),
                        iteration=4,
                        lam=80,
                        rank=200,
                        alpha=100,
                        gpu=True,
                        seed=1,
                        **unused):
    """
    Function used to achieve generalized projected lrec w/o item-attribute embedding
    :param matrix_train: user-item matrix with shape m*n
    :param embeded_matrix: item-attribute matrix with length n (each row represents one item)
    :param iteration: number of SVD iterations
    :param lam: parameter of penalty
    :param rank: the latent dimension/number of items
    :param alpha: weights of the U-I ratings
    :param gpu: whether use gpu power
    :return: prediction in sparse matrix
    """
    progress = WorkSplitter()
    matrix_input = matrix_train
    if embeded_matrix.shape[0] > 0:
        matrix_input = vstack((matrix_input, embeded_matrix.T))

    progress.subsection("Randomized SVD")
    start_time = time.time()
    P, sigma, Qt = randomized_svd(matrix_input, n_components=rank, n_iter=iteration, random_state=seed)
    print("Elapsed: {0}".format(inhour(time.time() - start_time)))

    start_time = time.time()
    if gpu:
        import cupy as cp
        progress.subsection("Create Cacheable Matrices")
        # RQ = matrix_input.dot(sparse.csc_matrix(Qt).T).toarray()

        # sqrt sigma injection
        RQ = matrix_input.dot(sparse.csc_matrix(Qt.T * np.sqrt(sigma))).toarray()

        # Exact
        matrix_B = cp.array(RQ)
        matrix_BT = matrix_B.T
        matrix_A = matrix_BT.dot(matrix_B) + cp.array((lam * sparse.identity(rank, dtype=np.float32)).toarray())

        # Approx
        # matrix_A = cp.array(sparse.diags(sigma * sigma + lam).todense())
        # matrix_B = cp.array(P*sigma)
        # matrix_BT = cp.array(matrix_B.T)
        print("Elapsed: {0}".format(inhour(time.time() - start_time)))


        progress.subsection("Item-wised Optimization")
        start_time = time.time()

        # For loop
        m, n = matrix_train.shape
        Y = []
        alpha = cp.array(alpha, dtype=cp.float32)
        for i in tqdm(xrange(n)):
            vector_r = matrix_train[:, i]
            vector_y = per_item_gpu(vector_r, matrix_A, matrix_B, matrix_BT, alpha)
            y_i_gpu = cp.asnumpy(vector_y)
            y_i_cpu = np.copy(y_i_gpu)
            Y.append(y_i_cpu)
        Y = scipy.vstack(Y)
        print("Elapsed: {0}".format(inhour(time.time() - start_time)))
    else:
        progress.subsection("Create Cacheable Matrices")
        RQ = matrix_input.dot(sparse.csc_matrix(Qt).T).toarray()

        # Exact
        matrix_B = RQ
        matrix_BT = RQ.T
        matrix_A = matrix_BT.dot(matrix_B) + (lam * sparse.identity(rank, dtype=np.float32)).toarray()

        # Approx
        # matrix_B = P * sigma
        # matrix_BT = matrix_B.T
        # matrix_A = sparse.diags(sigma * sigma - lam).todense()
        print("Elapsed: {0}".format(inhour(time.time() - start_time)))

        progress.subsection("Item-wised Optimization")
        start_time = time.time()

        # For loop
        m, n = matrix_train.shape
        Y = []
        for i in tqdm(xrange(n)):
            vector_r = matrix_train[:, i]
            vector_y = per_item_cpu(vector_r, matrix_A, matrix_B, matrix_BT, alpha)
            y_i_cpu = vector_y
            Y.append(y_i_cpu)
        Y = scipy.vstack(Y)
        print("Elapsed: {0}".format(inhour(time.time() - start_time)))
    return RQ, Y.T, None

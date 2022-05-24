from typing import Union, Dict

import numpy as np
from sklearn import clone
from sklearn.cross_decomposition import PLSRegression
from sklearn.utils import check_random_state
from sklearn.utils.validation import check_is_fitted
from sklearn.model_selection import cross_val_score
from joblib import Parallel, delayed

import warnings

from auswahl._base import PointSelector, IntervalSelector


class _VISSA:

    """
        Mixin for the VISSA feature selection method
    """

    def _produce_submodels(self, var_weights: np.array, n_submodels, random_state):
        n_feats = var_weights.shape[0]
        appearances = np.reshape(np.round(var_weights * n_submodels), (-1, 1))

        # populate Binary Sampling Matrix according to weights
        bsm = np.tile(np.arange(1, n_submodels + 1).reshape((1, -1)), [n_feats, 1])
        bsm = (bsm <= appearances)

        # create permutation for each a row of the Binary Sampling Matrix
        p = np.arange(n_submodels * n_feats)
        random_state.shuffle(p)
        p = np.reshape(p, (n_feats, n_submodels))
        p = np.reshape(np.argsort(p, axis=1), (-1,))
        row_selector = np.repeat(np.arange(n_feats), n_submodels)

        # permute the Binary Sampling Matrix
        return np.reshape(bsm[(row_selector, p)], (n_feats, n_submodels))

    def _evaluate(self, X, y, pls, submodel_index):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cv_scores = cross_val_score(pls,
                                        X,
                                        y,
                                        cv=self.n_cv_folds,
                                        scoring='neg_mean_squared_error')
        return np.mean(cv_scores), submodel_index

    def _evaluate_submodels(self, X, y, pls, bsm):
        submodels = Parallel(n_jobs=self.n_jobs)(delayed(self._evaluate)(X[:, bsm[:, i]],
                                                                         y,
                                                                         PLSRegression() if pls is None else clone(pls),
                                                                         i) for i in range(self.n_submodels))
        return submodels

    def _yield_best_weights(self, X, y, var_weights, n_submodels, random_state, selection_quantile):
        best_score = -10000000
        best_var_weights = None
        for i in range(5): #while True:
            print("Inner iteration")
            #produce weighted binary sampling matrix
            bsm = self._produce_submodels(var_weights, n_submodels, random_state)
            print('-->BSM done')
            # score submodels
            submodels = self._evaluate_submodels(X, y, self.pls, bsm)
            submodels_sorted = sorted(submodels, key=lambda x: -x[0])
            print('-->Eval done')
            # get submodel indices and scores of best submodels
            top_scores, top_models = list(zip(*(submodels_sorted[: selection_quantile])))
            # get average score of best submodels
            avg_top_scores = np.mean(top_scores)

            if avg_top_scores > best_score:
                best_score = avg_top_scores
                best_var_weights = np.sum(bsm[:, top_models], axis=1) / selection_quantile
            else:
                break

        return best_score, best_var_weights


class VISSA(PointSelector, _VISSA):

    """
        Feature Selection with Variable Iterative Space Shrinkage Approach (VISSA).

        The variable importance is calculated according to  Deng et al. [1]_.

        Read more in the :ref:`User Guide <vip>`.

        Parameters
        ----------
        n_features_to_select : int or float, default=None
            Number of features to select.

        n_jobs : int, default=1
            Number of parallel threads to calculate VISSA

        n_submodels : int, default=1000
            Number of submodels fitted in each VISSA iteration

        n_cv_folds : int, default=5
            Number of cross validation folds used in the evaluation of feature sets.

        pls : PLSRegression, default=None
            Estimator instance of the :py:class:`PLSRegression <sklearn.cross_decomposition.PLSRegression>` class.
            Use this to adjust the hyperparameters of the PLS method.


        Attributes
        ----------
        weights_ : ndarray of shape (n_features,)
            VISSA importance scores for variables.

        support_ : ndarray of shape (n_features,)
            Mask of selected features. The highest weighted features are selected

        References
        ----------
        .. [1] Bai-chuan Deng, Yong-huan Yun, Yi-zeng Liang, Lun-shao Yi,
               'A novel variable selection approach that iteratively optimizes variable space using weighted binary
                matrix sampling',
               Analyst, 139, 4836–-4845, 2014.

        Examples
        --------
        >>> import numpy as np
        >>> from auswahl import VISSA
        >>> X = np.random.randn(100, 10)
        >>> y = 5 * X[:, 0] - 2 * X[:, 5]  # y only depends on two features
        >>> selector = VISSA(n_features_to_select=2, n_jobs=2, n_submodels=200)
        >>> selector.fit(X, y)
        >>> selector.get_support()
        array([True, False, False, False, False, True, False, False, False, False])
    """

    def __init__(self,
                 n_features_to_select: int = None,
                 n_submodels: int = 1000,
                 n_jobs: int = 1,
                 n_cv_folds: int = 5,
                 pls: PLSRegression = None,
                 random_state: Union[int, np.random.RandomState] = None):

        super().__init__(n_features_to_select)

        self.pls = pls
        self.n_submodels = n_submodels
        self.n_jobs = n_jobs
        self.n_cv_folds = n_cv_folds
        self.random_state = random_state

    def _fit(self, X, y, n_features_to_select):
        random_state = check_random_state(self.random_state)

        # number of top models to used to update the weights of features
        selection_quantile = int(0.05 * self.n_submodels)
        n_subs = self.n_submodels

        top_score = -10000000
        top_var_weights = 0.5 * np.ones((X.shape[1],))
        while True:
            score, var_weights = self._yield_best_weights(X,
                                                          y,
                                                          top_var_weights,
                                                          n_subs,
                                                          random_state,
                                                          selection_quantile)
            if score > top_score:
                top_score = score
                top_var_weights = var_weights
            else:
                break

            # early stopping: the requested number of features have probability of ca. 1
            if np.sum(var_weights >= ((n_subs - 0.5)/n_subs)) >= n_features_to_select:
                break

        self.weights_ = var_weights
        self.support_ = np.zeros(X.shape[1]).astype('bool')
        self.support_[np.argsort(-var_weights)[: n_features_to_select]] = True

    def _get_support_mask(self):
        check_is_fitted(self)
        return self.support_


class iVISSA(IntervalSelector, _VISSA):

    def __init__(self,
                 n_intervals_to_select: int = 1,
                 interval_width: Union[int, float] = None,
                 n_submodels: int = 1000,
                 n_jobs: int = 1,
                 n_cv_folds: int = 5,
                 pls: PLSRegression = None,
                 random_state: Union[int, np.random.RandomState] = None):

        super().__init__(n_intervals_to_select, interval_width)

        self.pls = pls
        self.n_submodels = n_submodels
        self.n_jobs = n_jobs
        self.n_cv_folds = n_cv_folds
        self.random_state = random_state

    def _newly_selected(self, var_weights, next_var_weights, n_submodels):
        """
            Calculates features, which have been newly selected (weight of ca. 1)
        """
        old_selected = np.nonzero(var_weights >= (n_submodels - 0.5) / n_submodels)[0]
        new_selected = np.nonzero(next_var_weights >= (n_submodels - 0.5) / n_submodels)[0]
        return new_selected, np.setdiff1d(new_selected, old_selected)

    def _expand_interval(self,
                         X,
                         y,
                         var_weights,
                         score,
                         features,
                         new_feature,
                         n_submodels):
        threshold = (n_submodels - 0.5) / n_submodels
        features = features.tolist()
        # interleaved expansion on both sides
        borders = [new_feature - 1, new_feature + 1]
        limits = [0, -(X.shape[1] - 1)]
        index = 0
        progress = True
        while True:
            if borders[index] >= limits[index]:
                if var_weights[borders[index]] >= threshold:
                    borders[index] += (1 - index) * -1 + index * 1
                    progress = True
                else:
                    feature_score, _ = self._evaluate(X[:, features + [borders[index]]], y,
                                                      PLSRegression() if self.pls is None else clone(self.pls),
                                                      None)
                    if feature_score > score:
                        score = feature_score
                        features.append(borders[index])
                        var_weights[borders[index]] = 1  # mark the feature as selected
                        borders[index] += (1 - index) * -1 + index * 1
                        progress = True

            if index == 1 and not progress:
                break
            elif index == 1:
                progress = False

            index = (index + 1) % 2

        return features, score

    def _grow_intervals(self, X, y, var_weights, next_var_weights, score, n_submodels):
        features, new_features = self._newly_selected(var_weights, next_var_weights, n_submodels)
        for i in range(new_features.size):  # expand intervals around newly selected variables
            features, score = self._expand_interval(X, y,
                                                    next_var_weights, score,
                                                    features, new_features[i], n_submodels)
        return next_var_weights, score

    def _extract_intervals(self):
        # TODO: at first check general functinality
        ...

    def _fit(self, X, y, n_intervals_to_select, interval_width):
        random_state = check_random_state(self.random_state)

        # number of top models to be used to update the weights of features
        selection_quantile = int(0.05 * self.n_submodels)
        n_subs = self.n_submodels

        top_score = -10000000
        top_var_weights = 0.5 * np.ones((X.shape[1],))
        while True:
            score, var_weights = self._yield_best_weights(X,
                                                          y,
                                                          top_var_weights,
                                                          n_subs,
                                                          random_state,
                                                          selection_quantile)
            if score > top_score:
                var_weights, score = self._grow_intervals(X, y, top_var_weights, var_weights, score, n_subs)
                top_score = score
                top_var_weights = var_weights
            else:
                break

        # preliminarily
        self.weights_ = var_weights
        self.support_ = np.zeros(X.shape[1]).astype('bool')
        self.support_[np.argsort(-var_weights)[: n_intervals_to_select * interval_width]] = True
        # TODO: extract intervals

    def _get_support_mask(self):
        check_is_fitted(self)
        return self.support_



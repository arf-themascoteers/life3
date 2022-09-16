import numpy as np

from .data_handling import DataHandler
from abc import ABCMeta, abstractmethod


class StabilityScore(metaclass=ABCMeta):

    """
        Base class for all stability scores useable by the benchmarking system

        Parameters
        ----------
        metric_name: str, default=None
            Unique Name of the metric. If no name is provided, the name of the class inheriting from this function
            is used

    """

    def __init__(self, metric_name: str):
        if metric_name is not None:
            self.metric_name = metric_name
        else:
            self.metric_name = type(self).__name__

    @abstractmethod
    def __call__(self, pod: DataHandler):
        """
            Conducts the evaluation of the stability metric across all datasets and methods in the
            :class:`~auswahl.benchmarking.DataHandler` object, which is extended with the results of the
            stability evaluation.
        """
        ...


class PairwiseStabilityScore(StabilityScore, metaclass=ABCMeta):

    """
        The class provides the infrastructure for the introduction of new symmetric and pairwise defined
        stability metrics.
        The class handles the calculation of a pairwise stability assessment function across all pairs of feature selections
        generated by an algorithm, the appropriate average fusion and storage of the results
        in the provided :class:`~auswahl.benchmarking.DataHandler` object. The scores are calculated for every method,
        every dataset and every feature configuration in the :class:`~auswahl.benchmarking.DataHandler` object.

    """

    # go
    def _pairwise_scoring(self, pod: DataHandler):
        """The function handles the calculation of a pairwise stability assessment function across all pairs of feature selections
        generated by an algorithm, the appropriate average fusion and storage of the results
        in the provided :class:`~auswahl.benchmarking.DataHandler` object. The scores are calculated for every method,
        every dataset and every feature configuration in the :class:`~auswahl.benchmarking.DataHandler` object.

        Parameters
        ----------
        pod: DataHandler
            :class:`~auswahl.benchmarking.DataHandler` instance generated by :func:`~auswahl.benchmarking.benchmark`
        """
        r = pod.n_runs
        for n in pod.feature_descriptors:  # FeatureDescriptor
            for method in pod.methods:
                for dataset in pod.datasets:
                    # retrieve the samples of selected features (list of objects of type Selection)
                    supports = pod.get_selection_data(method=method, n_features=n, dataset=dataset).to_numpy().tolist()
                    supports = np.array([selection.features for selection in supports])
                    # evaluate all different pairs (symmetry assumed)
                    pairwise_sim = []
                    dim0, dim1 = np.triu_indices(r)
                    for i in range(dim0.size):
                        if dim0[i] != dim1[i]:  # only consider similarity between different pairs of feature sets
                            pairwise_sim.append(self.pairwise_sim_func(pod,
                                                                       set_1=supports[dim0[i]],
                                                                       set_2=supports[dim1[i]],
                                                                       dataset=dataset))
                    score = np.mean(np.array(pairwise_sim))

                    pod._register_stability(method=method,
                                            n_features=n,
                                            dataset=dataset,
                                            metric_name=self.metric_name,
                                            value=score)

    # go
    def __call__(self, pod: DataHandler):
        return self._pairwise_scoring(pod)

    # go
    @abstractmethod
    def pairwise_sim_func(self, data: DataHandler, set_1: np.ndarray, set_2: np.ndarray, dataset: str) -> float:
        """Function calculating the stability score for a single pair of selections of features. The function has to
        return a float score and receive as arguments an instance of :class:`~auswahl.benchmarking.DataHandler`,
        the two selections as np.ndarrays containing the integer indices of the selected features and a string identifier
        of the dataset, which can be used in conjunction with the :class:`~auswahl.benchmarking.DataHandler` object            to retrieve possibly required meta information like properties of the data, such as the total number of features
        available.

        Parameters
        ----------
        data: DataHandler
            benchmarking results. Can be used in conjunction with argument data_name to retrieve possibly necessary
            meta information, such as properties of the data relevant for the considered stability.
        set_1: np.nadarray
            array of integer indices of selected features of shape (n_features_to_select,)
        set_2: np.nadarray
            array of integer indices of selected features of shape (n_features_to_select,)
        data_name: str
            name of the dataset for which the stability metric is evaluated

        Returns
        -------
        stability score for the given pair of selections: float

        """
        ...


class DengScore(PairwiseStabilityScore):

    """Wraps the calculation of the selection stability score for randomized selection methods, according to Deng et al. [1]_.

        Parameters
        ----------
        Parameters
        ----------
        metric_name: str, default="deng_score"
            Unique Name of the metric. If no name is provided, the name of the class inheriting from this function
            is used

        References
        ----------
        .. [1] Bai-Chuan Deng, Yong-Huan Yun, Pan Ma, Chen-Chen Li, Da-Bing Ren and Yi-Zeng Liang,
               'A new method for wavelength interval selection that intelligently optimizes the locations, widths
               and combination of intervals',
               Analyst, 6, 1876-1885, 2015.
        """

    def __init__(self, metric_name: str = "deng_score"):
        super().__init__(metric_name)

    def pairwise_sim_func(self, data: DataHandler, set_1: np.ndarray, set_2: np.ndarray, dataset) -> float:
        n_wavelengths = data.get_meta(dataset)[2][1]
        n = set_1.size
        e = n ** 2 / n_wavelengths
        return (np.intersect1d(set_1, set_2).size - e) / (n - e)


class ZucknickScore(PairwiseStabilityScore):
    """Wraps the calculation of the stability score according to Zucknick et al. [1]_. The stability score features a
    correlation-adjusting mechanism assessing stability not only with respect to
    set theoretical stabilities, but also according to the correlation between the features selected in different runs.

    Parameters
    ----------
    pod: DataHandler
        :class:`~auswahl.benchmarking.DataHandler` object containing the benchmarking data.

    References
    ----------
    .. [1] Zucknick, M., Richardson, S., Stronach, E.A.: Comparing the characteristics of
           gene expression profiles derived by univariate and multivariate classification methods.
           Stat. Appl. Genet. Molecular Biol. 7(1), 7 (2008)
    """

    def __init__(self, correlation_threshold: float = 0.8, metric_name: str = "zucknick_score"):
        super().__init__(metric_name)

        if 0 <= correlation_threshold <= 1:
            self.correlation_threshold = correlation_threshold
        else:
            raise ValueError(f'Argument correlation_threshold is required to be in [0, 1]')

    def _thresholded_correlation(self, spectra, support_1: np.array, support_2: np.array):
        set_diff = np.setdiff1d(support_2, support_1)
        if set_diff.size == 0:
            return 0
        diff_features = np.transpose(spectra[:, set_diff])  # features x observations
        sup1_features = np.transpose(spectra[:, support_1])
        correlation = np.abs(np.corrcoef(sup1_features, diff_features))
        correlation = correlation * (correlation >= self.correlation_threshold)
        return (1 / support_2.size) * np.sum(correlation[:support_1.size, support_1.size:])

    def pairwise_sim_func(self, data: DataHandler, set_1: np.ndarray, set_2: np.ndarray, dataset: str) -> float:
        n = set_1.size
        spectra = data.get_meta(dataset)[0]
        intersection_size = np.intersect1d(set_1, set_2).size
        union_size = 2 * n - intersection_size
        c_12 = self._thresholded_correlation(spectra, set_1, set_2)
        c_21 = self._thresholded_correlation(spectra, set_2, set_1)
        return (intersection_size + c_12 + c_21) / union_size


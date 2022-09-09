import os
import pickle
from functools import wraps
from typing import List, Union, Tuple

import numpy as np
import pandas as pd

from .helpers import Selection
from ..._base import FeatureDescriptor


def _identify_key_error(key, multiindex):
    for level, k in enumerate(key):
        if isinstance(k, slice):
            continue
        else:
            if not isinstance(k, list):
                k = [k]
            for item in k:
                res = multiindex.isin([item], level=level)
                if not np.any(res):
                    return f'Item {item if not isinstance(item, FeatureDescriptor) else item.org_key} ' \
                           f'not present in level {multiindex.names[level]}'
    return None


def _protected(func):
    @wraps(func)
    def _wrapper(s, *args, **kwargs):
        try:
            res, key, multiindex = func(s, *args, **kwargs)
        except KeyError as e:
            # tentative measure for future pandas versions
            raise KeyError() from e
        # current version of pandas requires that
        key_error = _identify_key_error(key, multiindex)
        if key_error is not None:
            raise KeyError(key_error)
        return res

    return _wrapper


class DataHandler:
    """Data handling class corralling data generated by the benchmarking of different wavelength selection methods.
    """

    def __init__(self,
                 datasets: List[str],
                 methods: List[str],
                 features: List[FeatureDescriptor],
                 reg_metrics: List[str],
                 stab_metrics: List[str],
                 n_runs: int):

        self.datasets = sorted(datasets)
        self.methods = sorted(methods)
        self.feature_descriptors = sorted(features)
        self.reg_metrics = sorted(reg_metrics)
        self.stab_metrics = sorted(stab_metrics)
        self.n_runs = n_runs
        self.n_datasets = len(datasets)

        # setup indices
        reg_index = pd.MultiIndex.from_product([datasets, features, reg_metrics,
                                                [i for i in range(n_runs)]],
                                               names=['dataset', 'n_features', 'regression_metric', 'run'])
        reg_index, _ = reg_index.sortlevel(level=0)

        stab_index = pd.MultiIndex.from_product([datasets, features, stab_metrics],
                                                names=['dataset', 'n_features', 'stability_metric'])
        stab_index, _ = stab_index.sortlevel(level=0)

        selection_index = pd.MultiIndex.from_product([datasets, features, [i for i in range(n_runs)]],
                                                     names=['dataset', 'n_features', 'run'])
        selection_index, _ = selection_index.sortlevel(level=0)

        measurement_index = pd.MultiIndex.from_product([datasets, features, [i for i in range(n_runs)]],
                                                       names=['dataset', 'n_features', 'run'])
        measurement_index, _ = measurement_index.sortlevel(level=0)

        # setup dataframes
        self.selection_data = pd.DataFrame([[Selection() for _ in range(selection_index.shape[0])] for _ in methods],
                                           index=self.methods,
                                           columns=selection_index)
        self.stab_data = pd.DataFrame(np.NaN * np.zeros((len(methods), stab_index.shape[0]), dtype='float'),
                                      index=self.methods,
                                      columns=stab_index)
        self.reg_data = pd.DataFrame(np.NaN * np.zeros((len(methods), reg_index.shape[0]), dtype='float'),
                                     index=self.methods,
                                     columns=reg_index)

        self.measurement_data = pd.DataFrame(
            np.NaN * np.zeros((len(methods), measurement_index.shape[0]), dtype='float'),
            index=self.methods,
            columns=measurement_index)

        # store, if interval descriptors should be resolved
        self.resolve_tuples = features[0].resolve_tuples
        self.meta = dict()

    # TODO: improve that
    def register_meta(self, dataset_meta: List[Tuple[np.array, np.array, str, float]]):
        if not isinstance(dataset_meta, list):
            dataset_meta = [dataset_meta]
        for x, y, name, _ in dataset_meta:
            self.meta[name] = (x, y, x.shape)

    # TODO: improve that
    def get_meta(self, dataset):
        """Provides meta information for each dataset.

        Parameters
        ----------
        dataset: str
            Name of the dataset, whose meta information is requested.

        Returns
        -------
        tuple
            (spectra, targets, (n_samples, n_wavelengths)).
        """
        return self.meta[dataset]

    def _feature_descriptor_conversion(self, features):
        return [FeatureDescriptor(feature, resolve_intervals=self.resolve_tuples) for feature in features]

    def _make_key(self,
                  dataset: Union[str, List[str]] = None,
                  method: Union[str, List[str]] = None,
                  n_features: Union[int, List[int]] = None,
                  **kwargs):

        # row index key:
        method_key = method if method is not None else slice(None)

        if n_features is not None and not isinstance(n_features, list):
            n_features = [n_features]

        # column index key:
        key = [dataset if dataset is not None else slice(None),
               self._feature_descriptor_conversion(n_features) if n_features is not None else slice(None)]

        for key_item in ['reg_metric', 'stab_metric', 'sample']:
            value = kwargs.pop(key_item, -1)
            if value != -1:
                key.append(value if value is not None else slice(None))
        return method_key, tuple(key)

    # go
    def _register_regression(self,
                             value,
                             dataset: str = None,
                             method: str = None,
                             n_features: FeatureDescriptor = None,
                             reg_metric: str = None,
                             sample: int = None):
        self.reg_data.loc[(method, (dataset, n_features, reg_metric, sample))] = value

    # go
    def _register_selection(self,
                            dataset: str,
                            method: str,
                            n_features: FeatureDescriptor,
                            sample: int,
                            selection: list):
        self.selection_data.loc[(method, (dataset, n_features, sample))].features = selection

    # go
    def _register_stability(self,
                            dataset: str,
                            method: str,
                            n_features: FeatureDescriptor,
                            metric_name: str,
                            value: float):
        self.stab_data.loc[(method, (dataset, n_features, metric_name))] = value

    # go
    def _register_measurement(self,
                              value,
                              dataset: str = None,
                              method: str = None,
                              n_features: FeatureDescriptor = None,
                              sample: int = None):
        self.measurement_data.loc[(method, (dataset, n_features, sample))] = value

    @_protected
    def get_regression_data(self,
                            dataset: Union[str, List[str]] = None,
                            method: Union[str, List[str]] = None,
                            n_features: Union[int, List[int], Tuple[int], List[Tuple[int]]] = None,
                            reg_metric: Union[str, List[str]] = None,
                            sample: Union[int, List[int]] = None) -> pd.DataFrame:
        """Retrieve data related to the regression performance of feature selection methods.

        Parameters
        ----------
        dataset: str or list of str, default=None
            Dataset identifier or list of dataset identifiers.

        method : str or list of str, default=None
            Method(s) to be retrieved. If None, all methods are retrieved.

        n_features : int, tuple of int, list of int or list of tuple of int, default=None
             Feature configuration for which to retrieve results. A configuration for a single number of
             features, a single interval defined as tuple (#intervals, interval_width) or lists of such configurations
             can be passed. If None, the runs for all numbers of selected features are retrieved.

        reg_metric : str or list of str, default=None
            Regression metric(s) to be retrieved. If None, all available metrics are retrieved.

        item : Literal of ['mean', 'std', 'median', 'max', 'min', 'samples'], default=None
            Specify, which indicator(s) for the selected regression metrics is to be retrieved. If None, all indicators
            are retrieved.

        Returns
        -------
        pandas multiIndex DataFrame.
            The frame holds the selection methods in its index and a multiindex with levels
            {'dataset', 'n_features', 'reg_metric', 'sample'} as columns, where 'sample' refers to the individual
            runs for the statistical evaluation. The keys for level 'n_features' are of type
            :class:`~auswahl.FeatureDescriptor`.
        """
        method_key, key = self._make_key(dataset, method, n_features, reg_metric=reg_metric, sample=sample)
        return self.reg_data.loc[(method_key, key)], key, self.reg_data.columns

    @_protected
    def get_selection_data(self,
                           dataset: Union[str, List[str]] = None,
                           method: Union[str, List[str]] = None,
                           n_features: Union[int, Tuple[int], List[int], List[Tuple[int]]] = None,
                           sample: Union[int, List[int]] = None) -> pd.DataFrame:
        """Retrieve data related to the regression performance of feature selection methods.

        Parameters
        ----------
        method : str or list of str, default=None
            Method(s) to be retrieved. If None, all methods are retrieved.

        n_features : int, tuple of int, list of int or list of tuple of int, default=None
             Feature configuration for which to retrieve results. A configuration for a single number of features, a
             single interval defined as tuple (#intervals, interval_width) or lists of such configurations can be
             passed. If None, the runs for all numbers of selected features are retrieved.

        sample_run : int or list of int, default=None
            The run(s) for which the selected features are to be retrieved. If None, the selected features of all runs
            are retrieved.

        Returns
        -------
        pandas.MultiIndex DataFrame.
            The frame holds the methods in its index and a multiindex with levels {'dataset', 'n_features', 'sample'} as
            columns, where 'sample' refers to the individual runs for the statistical evaluation. The keys for level
            'n_features' are of type :class:`~auswahl.FeatureDescriptor`. The type of the data in the frame is
            :class:`~auswahl.benchmarking.util.helpers.Selection`.
        """
        method_key, key = self._make_key(dataset, method, n_features, sample=sample)
        return self.selection_data.loc[(method_key, key)], key, self.selection_data.columns

    @_protected
    def get_stability_data(self,
                           dataset: Union[str, List[str]] = None,
                           method: Union[str, List[str]] = None,
                           n_features: Union[int, Tuple[int], List[int], List[Tuple[int]]] = None,
                           stab_metric: Union[str, List[str]] = None) -> pd.DataFrame:
        """Retrieve data related to the stability of feature selection methods.

        Parameters
        ----------
        method : str or list of str, default=None
            Method(s) to be retrieved. If None, all methods are retrieved.

        n_features : int, tuple of int, list of int or list of tuple of int, default=None
             Feature configuration for which to retrieve results. A configuration for a single number of features, a
             single interval defined as tuple (#intervals, interval_width) or lists of such configurations can be
             passed. If None, the runs for all numbers of selected features are retrieved.

        stab_metric : str or list of str, default=None
            Stability metric(s) to be retrieved. If None, all available metrics are retrieved.

        Returns
        -------
        pandas multiIndex DataFrame.
            The frame holds the selection methods in its index and a multiindex with levels
            {'dataset', 'n_features', 'stab_metric'} as columns. The keys for level 'n_features' are of type
            :class:`~auswahl.FeatureDescriptor`.
        """
        method_key, key = self._make_key(dataset, method, n_features, stab_metric=stab_metric)
        return self.stab_data.loc[(method_key, key)], key, self.stab_data.columns

    @_protected
    def get_measurement_data(self,
                             dataset: Union[str, List[str]] = None,
                             method: Union[str, List[str]] = None,
                             n_features: Union[int, List[int], Tuple[int], List[Tuple[int]]] = None,
                             sample: Union[int, List[int]] = None):
        """Retrieve data related to the stability of feature selection methods.

        Parameters
        ----------
        method : str or list of str, default=None
            Method(s) to be retrieved. If None, all methods are retrieved.

        n_features : int, tuple of int, list of int or list of tuple of int, default=None
             Feature configuration for which to retrieve results. A configuration for a single number of features, a
             single interval defined as tuple (#intervals, interval_width) or lists of such configurations can be
             passed. If None, the runs for all numbers of selected features are retrieved.

        sample_run : int or list of int, default=None
            The run(s) for which the selected features are to be retrieved. If None, the selected features of all runs
            are retrieved.

        Returns
        -------
        pandas multiIndex DataFrame.
            The frame holds the methods in its index and a multiindex with levels {'dataset', 'n_features', 'sample'} as
            columns, where 'sample' refers to the individual runs for the statistical evaluation. The keys for level
            'n_features' are of type :class:`~auswahl.FeatureDescriptor`.
        """

        method_key, key = self._make_key(dataset, method, n_features, sample=sample)
        return self.measurement_data.loc[(method_key, key)], key, self.measurement_data.columns

    def store(self, file_path: str, file_name: str):
        """Stores the DataHandler object as pickle file.

        Parameters
        ----------
        file_path: str
            Path to the file.

        file_name: str
            Name of the file without extension.
        """
        if '.' in file_name:
            file_name = file_name.split('.')[0]
        path = os.path.join(file_path, f'{file_name}.pickle')
        with open(path, 'wb') as file:
            pickle.dump(self, file)
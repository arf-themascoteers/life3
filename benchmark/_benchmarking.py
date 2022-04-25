import numpy as np
import timeit as tt

from numpy.random import RandomState
from typing import Union, List
from sklearn.utils import check_random_state
from sklearn.model_selection import train_test_split
from sklearn.base import BaseEstimator
from sklearn import clone

from auswahl import PointSelector, IntervalSelector
from benchmark.util._data_handling import BenchmarkPOD
from benchmark.util._metrics import mean_std_statistics


def benchmark(data_x: np.array,
              data_y: np.array,
              n_runs: int,
              train_size: Union[int, float],
              test_model: BaseEstimator,
              reg_metrics: List,
              stability_metrics: List,
              methods: List[Union[PointSelector, IntervalSelector]],
              random_state: Union[int, RandomState]):

    methods = sorted([(type(method).__name__, method) for method in methods], key=lambda tup: tup[0])
    metrics = [(metric.__name__, metric) for metric in (reg_metrics if type(reg_metrics) == list else [reg_metrics])]

    random_state = check_random_state(random_state)

    pod = BenchmarkPOD()
    pod.register_meta(n_samples=data_x.shape[0], n_wavelengths=data_x.shape[1])

    # TODO: parallelization with argument n-jobs (produce seeds beforehand to avoid scheduling related reproducilbility issues)
    # parallelization of the outer loop: Due to different methods having different
    # runtimes, a parallelization at this level woud yield with high probability idlying threads
    # => avoids unnecessary synchronization between threads
    for r in range(n_runs):
        seed = random_state.randint(0, 1000000)
        train_x, test_x, train_y, test_y = train_test_split(data_x, data_y, train_size=train_size, random_state=seed)
        for method_name, method in methods:
            if hasattr(method, 'random_state'):
                method.random_state = seed

            # TODO: fix exec time measurement
            exec_time = 0
            #tt.timeit(lambda: method.fit(train_x, train_y))

            method.fit(train_x, train_y)
            support = method.get_support(indices=True)

            test_regressor = clone(test_model)
            test_regressor.fit(train_x[:, support], train_y)
            prediction = test_regressor.predict(test_x[:, support])

            for metric_name, metric in metrics:
                pod.register(method_name, 'metrics', metric_name, samples=metric(test_y, prediction))

            pod.register(method_name, time=exec_time, support=support)

    # mean and std over all metrics and runs
    mean_std_statistics(pod)

    # stability scores
    for stab_metric in stability_metrics:
        stab_metric(pod)

    return pod
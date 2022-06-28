
import numpy as np
import pandas as pd
import matplotlib.patches as mpatches

from typing import List, Union, Literal, Tuple
from matplotlib import pyplot as plt

from ._data_handling import BenchmarkPOD


def _check_specified_or_singleton(pool, identifier):
    if identifier is None:
        if len(pool) > 1:
            raise ValueError("Dataset is ambiguous. Specify a dataset")
        return pool[0]
    return identifier


def _arrange_boxes(pod, n_features, methods):
    x_coords = []
    ticks = np.arange(len(n_features) if n_features is not None else len(pod.n_features)) + 1  #start with 1
    n_methods = len(methods if methods is not None else pod.methods)
    for i in range(n_methods):
        x_coords.append(-0.1 + ticks + (0.2 / (n_methods - 1)) * i)
    return x_coords, ticks


def _box_plot(title: str,
              x_label: str,
              y_label: str,
              y_data: List[List[float]],
              x_data: List[float],
              legend: List[str],
              save_path: str = None):

    # TODO: color strategies
    colors = ['k', 'b', 'g', 'r', 'c', 'm', 'y']
    entities = ['boxprops', 'medianprops', 'flierprops', 'capprops', 'whiskerprops']

    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(10, 5))
    legend_handles = []

    if legend is None:
        plotting_kwargs = dict()
        for entity in entities:
            plotting_kwargs[entity] = dict(color='k')

    for i, data in enumerate(y_data):
        if legend is not None:
            plotting_kwargs = dict()
            for entity in entities:
                plotting_kwargs[entity] = dict(color=colors[i])

        ax.boxplot(data, positions=[x_data[i]], whis=(0, 100), widths=0.05, manage_ticks=False, **plotting_kwargs)
        if legend is not None:
            legend_handles.append(mpatches.Patch(color=colors[i], label=legend[i]))

    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    if legend is not None:
        ax.legend(handles=legend_handles)

    if save_path is not None:
        plt.savefig(save_path)
    plt.show()

def _errorbar_plot(title: str,
                   x_label: str,
                   y_label: str,
                   y_data: List[List[float]],
                   y_max: List[List[float]],
                   y_min: List[List[float]],
                   x_data: List[List[Union[float, int]]],
                   tick_labels: List[List[Union[float, int]]],
                   ticks: List[Union[int, float]],
                   legend: List[str],
                   plot_lines: bool = True,
                   save_path: str = None):

    # TODO: color strategies
    colors = ['k', 'b', 'g', 'r', 'c', 'm', 'y']
    markers = [c for c in ".ov^<>12348sp*hH+xDd|"]

    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(10, 5))
    legend_handles = []
    for i, y in enumerate(y_data):
        ax.errorbar(x_data[i] if len(x_data) > 1 else x_data[0],
                    y,
                    yerr=[y_min[i], y_max[i]],
                    color=colors[i],
                    marker=markers[i],
                    linestyle='dotted' if plot_lines else 'none')
        legend_handles.append(mpatches.Patch(color=colors[i], label=legend[i]))

    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_xticklabels(tick_labels)
    ax.set_xticks(ticks)
    ax.legend(handles=legend_handles)

    if save_path is not None:
        plt.savefig(save_path)
    plt.show()

def _line_plot(title: str,
               x_label: str,
               y_label: str,
               y_data: List[List[float]],
               x_data: List[List[Union[float, int]]],
               legend: List[str],
               save_path: str = None):

    # TODO: color strategies
    colors = ['k', 'b', 'g', 'r', 'c', 'm', 'y']
    markers = [c for c in ".ov^<>12348sp*hH+xDd|"]

    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(10, 5))
    legend_handles = []

    for i, y_data in enumerate(y_data):
        ax.errorbar(x_data[i] if len(x_data) > 1 else x_data[0],
                    y_data,
                    color=colors[i],
                    marker=markers[i])
        legend_handles.append(mpatches.Patch(color=colors[i], label=legend[i]))

    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.legend(handles=legend_handles)

    if save_path is not None:
        plt.savefig(save_path)
    plt.show()


def plot_score_vs_stability(pod: BenchmarkPOD,
                            dataset: str,
                            n_features: Union[int, Tuple[int]],
                            stability_metric: str,
                            regression_metric: str,
                            methods: Union[str, List[str]] = None,
                            save_path: str = None):
    """
        Plotting a boxplot for the benchmarked methods displaying
            * the mean regression score on the y-axis
                * mean regression value
                * (25,75) IQR as box
                * (0, 100) range as whiskers
            * the stability score on the x-axis

        Parameters
        ----------

        pod : BenchmarkPOD
            data container produced by benchmarking

        dataset: str
            dataset for which the data is to be plotted

        n_features: int or tuple of int
            number of features, which were to be selected by the algorithms

        stability_metric : str
            identifier of the stability metric to be plotted in the pod

        regression_metric : str
            identifier of the regression metric to be plotted in the pod

        methods : str or list of str, default=None
            identifers of methods for which the data is to be plotted. If None, all available methods are plotted

        save_path: str, default=None
            path at which the plot is stored. If None, the plot is just displayed
    """

    regression_scores = []
    stability_scores = []

    if methods is None:
        methods = pod.methods
    elif type(methods) == str:
        methods = [methods]

    for i, method in enumerate(methods):
        regression_scores.append(pod.get_regression_data(method=method,
                                                         n_features=n_features,
                                                         reg_metric=regression_metric,
                                                         item='samples'))
        stability_scores.append(pod.get_stability_data(dataset=dataset,
                                                       method=method,
                                                       n_features=n_features,
                                                       stab_metric=stability_metric))
    _box_plot("Regression-Stability-Plot",
              stability_metric,
              regression_metric,
              regression_scores,
              stability_scores,
              pod.methods,
              save_path)


def plot_exec_time(pod: BenchmarkPOD,
                   dataset: str = None,
                   methods: Union[str, List[str]] = None,
                   n_features: List[Union[int, Tuple[int]]] = None,
                   item: Literal['mean', 'median'] = 'mean',
                   save_path: str = None):

    """

        Parameters
        ----------
    pod: BenchmarkPOD
        BenchmarkPOD object containing the benchmarking data
    dataset: str, default=None
        identifier of the dataset of which to plot the execution time. If there is data for only one dataset
        in the the BenchmarkPOD object, the argument does not have to be specified
    methods: str or list of str
        identifiers of methods for which to plot the execution time
    n_features: list of integers or of tuples of integers
        identifiers of the number of features or the configuration of intervals for which the execution time is to be plotted
    item: Literal['mean', 'median']
        specifies whether the mean or median is displayed in the plot
    save_path: str
        path at which the plot has to be saved

    """

    dataset = _check_specified_or_singleton(pod.datasets, dataset)

    if n_features is not None and not isinstance(n_features, list):
        n_features = [n_features]

    exec_times = pod.get_measurement_data(dataset=dataset,
                                          method=methods,
                                          n_features=n_features,
                                          item=item).to_numpy().tolist()

    exec_mins = pod.get_measurement_data(dataset=dataset,
                                         method=methods,
                                         n_features=n_features,
                                         item='min').to_numpy().tolist()

    exec_max = pod.get_measurement_data(dataset=dataset,
                                        method=methods,
                                        n_features=n_features,
                                        item='max').to_numpy().tolist()

    x_coords, ticks = _arrange_boxes(pod, n_features, methods)

    _errorbar_plot(f'Execution time: {item} and ranges',
                   "n_features",
                   "Execution time [s]",
                   exec_times,
                   exec_max,
                   exec_mins,
                   x_coords,
                   n_features if n_features is not None else pod.n_features,
                   ticks,
                   methods if methods is not None else pod.methods,
                   save_path)


def plot_score(pod: BenchmarkPOD,
               dataset: str = None,
               regression_metric: str = None,
               methods: Union[str, List[str]] = None,
               n_features: List[Union[int, Tuple[int, int]]] = None,
               item: Literal['mean', 'median'] = 'mean',
               save_path: str = None):

    regression_metric = _check_specified_or_singleton(pod.reg_metrics, regression_metric)
    dataset = _check_specified_or_singleton(pod.datasets, dataset)

    if n_features is not None and not isinstance(n_features, list):
        n_features = [n_features]

    reg_scores = pod.get_regression_data(method=methods,
                                         n_features=n_features,
                                         dataset=dataset,
                                         reg_metric=regression_metric,
                                         item=item).to_numpy().tolist()

    reg_mins = pod.get_regression_data(method=methods,
                                       dataset=dataset,
                                       n_features=n_features,
                                       reg_metric=regression_metric,
                                       item='min').to_numpy().tolist()

    reg_max = pod.get_regression_data(method=methods,
                                      dataset=dataset,
                                      n_features=n_features,
                                      reg_metric=regression_metric,
                                      item='max').to_numpy().tolist()

    # calculate offset x coordinates
    x_coords, ticks = _arrange_boxes(pod, n_features, methods)

    _errorbar_plot(f'Regression performance: {item} and range on dataset {dataset}',
                   "n_features",
                   regression_metric,
                   reg_scores,
                   reg_max,
                   reg_mins,
                   x_coords,
                   n_features if n_features is not None else pod.n_features,
                   ticks,
                   methods if methods is not None else pod.methods,
                   plot_lines=False,
                   save_path=save_path
                   )

def plot_stability_series(pod: BenchmarkPOD,
                          dataset: str,
                          stability_metric: str,
                          methods: Union[str, List[str]] = None,
                          save_path: str = None):

    """
        Plots the stability score of methods for a given metric across the number of features to be selected

        Parameters
        ----------
        pod: BenchmarkPOD
            BenchmarkPOD object containing the benchmarking data
        dataset: str
            dataset identifier
        stability_metric: str
            stability metric used for plotting
        methods: Union[str, List[str]], default=None
            method identifier or list of method identifiers for methods to be plotted. If None, all available methods
            are plotted
        save_path: str, default=None
            path on which to store the plot. If None, the plot is simply displayed

    """

    y_data = pod.get_stability_data(method=methods, dataset=dataset, stab_metric=stability_metric).to_numpy().tolist()
    x_data = [pod.n_features]

    _line_plot(f'Stability across n_features to select: Dataset {dataset}',
               "n_features",
               stability_metric,
               y_data,
               x_data,
               pod.methods,
               save_path)


def _plot_selection_bar(pod: BenchmarkPOD,
                        dataset: str,
                        n_features: int,
                        methods: Union[str, List[str]] = None,
                        save_path: str = None):

    colors = ['darkorange', 'cornflowerblue']

    fig = plt.figure()
    gs = fig.add_gridspec(len(methods), hspace=0)
    axs = gs.subplots(sharex=True, sharey=True)
    fig.suptitle(f'Displaying selection probability P on dataset {dataset} for {n_features} features to be selected')

    selections = pod.get_selection_data(dataset=dataset, method=methods, n_features=n_features)
    n_wavelengths = pod.get_meta(dataset)[2][1]

    if len(methods) == 1:
        axs = [axs]

    for i in range(len(methods)):

        unique_counts = selections.iloc[i].value_counts()
        bar_heights = np.zeros((n_wavelengths,))
        bar_heights[unique_counts.index.to_numpy().astype('int')] = unique_counts.to_numpy()

        axs[i].bar(np.arange(n_wavelengths), bar_heights / pod.n_runs, color=colors[i % 2])
        if i % 2 == 0:  # distribute y-axis ticks between left and right hand side
            axs[i].yaxis.tick_right()
        else:
            axs[i].yaxis.set_label_position("right")

        axs[i].set_xlabel("wavelength")
        axs[i].set_ylabel("P")

        axs[i].legend(handles=[mpatches.Patch(color=colors[i % 2], label=methods[i])])

    # Hide x labels and tick labels for all but bottom plot.
    for ax in axs:
        ax.label_outer()

    if save_path is not None:
        plt.savefig(save_path)
    plt.show()


def _plot_selection_heatmap(pod: BenchmarkPOD,
                            dataset: str,
                            n_features: int,
                            methods: Union[str, List[str]] = None,
                            save_path: str = None):

    fig, ax = plt.subplots()
    ax.set_title(f'Displaying selection probability heatmap on dataset {dataset} for {n_features} features to be selected')

    selections = pod.get_selection_data(dataset=dataset, method=methods, n_features=n_features)
    n_wavelengths = pod.get_meta(dataset)[2][1]

    selection_prob = np.zeros((len(methods), n_wavelengths))
    for i in range(len(methods)):
        unique_counts = selections.iloc[i].value_counts()
        selection_prob[i, unique_counts.index.to_numpy().astype('int')] = unique_counts.to_numpy() / pod.n_runs

    #build heatmap
    print(selection_prob)
    ax.imshow(selection_prob, cmap='viridis')

    #add annotations
    ax.set_xlabel('wavelength')
    ax.set_ylabel('method')
    ax.set_yticks(np.arange(len(methods)), labels=methods)
    ax.set_xlabel(np.arange(n_wavelengths))

    if save_path is not None:
        plt.savefig(save_path)
    plt.show()


def plot_selection(pod: BenchmarkPOD,
                   dataset: str,
                   n_features: int,
                   methods: Union[str, List[str]] = None,
                   plot_type: Literal['heatmap', 'bar'] = 'bar',
                   save_path: str = None):

    if methods is None:
        methods = pod.methods
    if type(methods) == str:
        methods = [methods]

    if plot_type == 'bar':
        _plot_selection_bar(pod, dataset, n_features, methods, save_path)
    elif plot_type == 'heatmap':
        _plot_selection_heatmap(pod, dataset, n_features, methods, save_path)
    else:
        raise ValueError(f'Unknown plot_type passed to function plot_selection: {plot_type}.'
                         'Use one of {heatmap, bar}')

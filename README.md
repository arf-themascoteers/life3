# nirSelect
Collection of Feature Selection Methods for Near-Infrared Spectroscopy

## Scope
This library provides a collection of supervised feature selection methods for near-infrared spectra.
(Note, that features are also called variables of simply wavelengths in the field of chemometrics.)
It does **not** provide any preprocessing methods or calibration models.
All features selection methods have been implemented in compliance with the sklearn library.
Thus, the methods can be used in a sklearn pipeline before an estimator.

## Methods
The libraray provides methods for selecting wavelengths without spatial constraints and methods for selecting continuous bands of wavelengths.
The following methods are implemented:
* Wavelength Point Selection: VIP, MC-UVE, CARS
* Wavelength Interval Selection: I-RF

## Installation

```
pip install nirSelect
```

## Usage
```python
from nirSelect import CARS

cars = CARS(n_features=20, random_state=42)
cars.fit(my_spectra, my_targets)

feature_mask = cars.get_support()
```

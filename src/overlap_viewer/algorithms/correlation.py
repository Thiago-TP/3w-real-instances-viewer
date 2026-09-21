"""How the sensors move together over a set of instances: Pearson, mutual information, and what smoothing does. Numpy only, the mutual information through the ``analysis`` extra.

Melo's exploratory methodology (doctoral thesis, section 4.1.5) reads the
relations between the variables of a dataset three ways at once. The
**Pearson coefficient** is the linear correlation. The **mutual-information
coefficient** is a nonlinear one: the mutual information *I* of two
variables, estimated by nearest neighbours (Kraskov, Stögbauer and
Grassberger's estimator, which ``ennemi`` and scikit-learn both implement),
turned into a coefficient between 0 and 1 by Laarne *et al.*'s normalisation,
``ρ_I = sqrt(1 − exp(−2 I))``, which equals the Pearson coefficient when the
two variables are jointly Gaussian. Zhang *et al.*'s **nonlinear
coefficient** is what the second says beyond the first, ``r = ρ_I (1 − |ρ|)``.
Over a whole set of variables the thesis sums each into a global figure
(equations 4.15 and 4.16): ``ρ = sqrt((Σ ρ_ij² − m) / (m² − m))`` and
``r = sqrt(Σ r_ij² / (m² − m))`` over the ``m × m`` matrix.

Two of the thesis's findings shape this module. Smoothing the series with a
moving average raises both coefficients, because noise hides the relations
(its figures 4.11 and 4.26), so every matrix is computed for several
window lengths at once and the page slides between them. And on 3W the 1 Hz
grid is mostly straight lines the historian drew between measurements
(``algorithms.interpolation``), whose ups and downs show as correlations
that are not there (his figure 4.55); the smoothing is also what flattens
them, and the caption says so.

The Pearson coefficients are exact over every co-valid sample of the
instances in the scope, accumulated as running sums so that a scope of a
million samples costs a pass and no memory. The mutual information is
estimated on an even subsample of the same samples, a few thousand rows,
which is what the estimator handles in a second and enough for a coefficient
read to two digits. Samples are pooled across the instances of the scope,
which is what a correlation *over a class* or *over a well* means here; a
scope that mixes wells mixes their levels, and the help says what that does.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from overlap_viewer.backend.extras import available

# The moving-average windows, in samples (seconds), the matrices are computed
# for: none, then the scales of the historian's ramps and of the noise.
WINDOWS = (1, 5, 15, 60, 300)
WINDOW_NAMES = {1: "no smoothing", 5: "5 s", 15: "15 s", 60: "1 min", 300: "5 min"}
COEFFICIENTS = ("Pearson", "Mutual information", "Nonlinear")
# Fewer co-valid samples than this and a pair says nothing.
MIN_PAIRS = 300
# The subsample the mutual information is estimated on, over the whole scope.
MAX_MI_SAMPLES = 4000
MI_NEIGHBORS = 3


@dataclass(frozen=True)
class Correlations:
    """The three coefficients of every pair of sensors, per smoothing window.

    Every matrix is ``(sensors, sensors)`` and symmetric, NaN where a pair
    has fewer than ``MIN_PAIRS`` co-valid samples (or, for the mutual
    information, where the extra is missing). ``pairs`` counts the co-valid
    samples; ``n_instances`` how many events the scope pooled.
    """

    sensors: list[str]
    windows: tuple[int, ...]
    pearson: dict[int, np.ndarray]
    pairs: dict[int, np.ndarray]
    mi_coefficient: dict[int, np.ndarray] | None
    nonlinear: dict[int, np.ndarray] | None
    n_instances: int
    mi_samples: int = 0

    def matrix(self, coefficient: str, window: int) -> np.ndarray | None:
        if coefficient == "Pearson":
            return self.pearson.get(window)
        if coefficient == "Mutual information":
            return None if self.mi_coefficient is None else self.mi_coefficient.get(window)
        return None if self.nonlinear is None else self.nonlinear.get(window)

    def present(self, window: int) -> np.ndarray:
        """Which sensors have enough co-valid samples with at least one other sensor."""
        pairs = self.pairs[window].copy()
        np.fill_diagonal(pairs, 0)
        return (pairs >= MIN_PAIRS).any(axis=1)

    def global_coefficients(self, window: int) -> tuple[float, float]:
        """Melo's global linear and nonlinear coefficients (thesis eqs. 4.16 and 4.15) over the sensors present."""
        present = self.present(window)
        m = int(present.sum())
        if m < 2:
            return (float("nan"), float("nan"))
        rho = self.pearson[window][np.ix_(present, present)]
        rho_sum = float(np.nansum(rho**2))
        linear = float(np.sqrt(max(rho_sum - m, 0.0) / (m * m - m)))
        if self.nonlinear is None:
            return (linear, float("nan"))
        r = self.nonlinear[window][np.ix_(present, present)]
        nonlinear = float(np.sqrt(np.nansum(r**2) / (m * m - m)))
        return (linear, nonlinear)


def mi_coefficient(mutual_information: np.ndarray) -> np.ndarray:
    """Laarne's normalisation of a mutual information (in nats) into a coefficient between 0 and 1."""
    return np.sqrt(
        1.0 - np.exp(-2.0 * np.maximum(np.asarray(mutual_information, dtype=float), 0.0))
    )


def smooth(values: np.ndarray, window: int) -> np.ndarray:
    """A moving average of ``window`` samples, defined where the whole window has readings."""
    if window <= 1:
        return np.asarray(values, dtype=float)
    return (
        pd.DataFrame(np.asarray(values, dtype=float))
        .rolling(window, min_periods=window)
        .mean()
        .to_numpy()
    )


class CorrelationPass:
    """Accumulates the co-valid sums of every pair of sensors, per window, over the frames it is fed.

    ``budget`` is how many rows the mutual-information subsample may take in
    all, spread evenly over the ``n_instances`` the scope holds.
    """

    def __init__(
        self,
        sensors: Sequence[str],
        bounds: Sequence[tuple[float, float]],
        n_instances: int,
        windows: Sequence[int] = WINDOWS,
        budget: int = MAX_MI_SAMPLES,
    ):
        self.sensors = list(sensors)
        self.bounds = list(bounds)
        self.windows = tuple(windows)
        self.n_instances = max(int(n_instances), 1)
        self.per_instance = max(budget // self.n_instances, 8)
        s = len(self.sensors)
        self._n = {w: np.zeros((s, s)) for w in self.windows}
        self._sx = {w: np.zeros((s, s)) for w in self.windows}
        self._sxx = {w: np.zeros((s, s)) for w in self.windows}
        self._sxy = {w: np.zeros((s, s)) for w in self.windows}
        self._rows: dict[int, list[np.ndarray]] = {w: [] for w in self.windows}
        self.fed = 0

    def add(self, frame: pd.DataFrame) -> None:
        """Take one instance, or one merged recording."""
        s = len(self.sensors)
        raw = np.full((len(frame), s), np.nan)
        for j, name in enumerate(self.sensors):
            if name in frame.columns:
                values = frame[name].to_numpy(dtype=float)
                low, high = self.bounds[j]
                raw[:, j] = np.where((values < low) | (values > high), np.nan, values)
        for w in self.windows:
            X = smooth(raw, w) if w > 1 else raw
            valid = ~np.isnan(X)
            V = valid.astype(float)
            X0 = np.where(valid, X, 0.0)
            self._n[w] += V.T @ V
            self._sx[w] += X0.T @ V  # Σ x_i over the samples where i and j are both valid
            self._sxx[w] += (X0**2).T @ V
            self._sxy[w] += X0.T @ X0
            if len(X):
                stride = max(1, int(np.ceil(len(X) / self.per_instance)))
                # A copy: a strided view would keep the whole smoothed frame alive
                # for every instance and every window, gigabytes over a dataset.
                self._rows[w].append(X[::stride].copy())
        self.fed += 1

    def result(self, mutual_information: bool = True) -> Correlations:
        """The coefficients from what was fed; the mutual information only with the ``analysis`` extra."""
        pearson, pairs = {}, {}
        for w in self.windows:
            n, sx, sxx, sxy = self._n[w], self._sx[w], self._sxx[w], self._sxy[w]
            sy, syy = sx.T, sxx.T
            with np.errstate(invalid="ignore", divide="ignore"):
                cov = n * sxy - sx * sy
                var_x = n * sxx - sx**2
                var_y = n * syy - sy**2
                rho = cov / np.sqrt(var_x * var_y)
            rho = np.where(n >= MIN_PAIRS, rho, np.nan)
            rho = np.clip(rho, -1.0, 1.0)
            pearson[w] = rho
            pairs[w] = n
        mi = nonlinear = None
        mi_samples = 0
        if mutual_information and available("analysis"):
            mi, nonlinear = {}, {}
            for w in self.windows:
                rows = (
                    np.vstack(self._rows[w]) if self._rows[w] else np.zeros((0, len(self.sensors)))
                )
                mi_samples = max(mi_samples, len(rows))
                coefficient = self._mutual_information(rows, pairs[w])
                mi[w] = coefficient
                nonlinear[w] = coefficient * (1.0 - np.abs(pearson[w]))
        return Correlations(
            self.sensors, self.windows, pearson, pairs, mi, nonlinear, self.fed, mi_samples
        )

    def _mutual_information(self, rows: np.ndarray, pairs: np.ndarray) -> np.ndarray:
        """Laarne's coefficient of every pair with enough co-valid rows in the subsample."""
        from sklearn.feature_selection import mutual_info_regression

        s = len(self.sensors)
        out = np.full((s, s), np.nan)
        for i in range(s):
            out[i, i] = 1.0 if pairs[i, i] >= MIN_PAIRS else np.nan
            for j in range(i + 1, s):
                if pairs[i, j] < MIN_PAIRS:
                    continue
                both = ~np.isnan(rows[:, i]) & ~np.isnan(rows[:, j])
                if both.sum() < 2 * MI_NEIGHBORS + 2:
                    continue
                x, y = rows[both, i], rows[both, j]
                if x.std() <= 0 or y.std() <= 0:
                    continue
                info = mutual_info_regression(
                    x[:, None], y, n_neighbors=MI_NEIGHBORS, random_state=0
                )[0]
                out[i, j] = out[j, i] = float(mi_coefficient(np.array([info]))[0])
        return out


@dataclass
class CorrelationScope:
    """What a correlation matrix was taken over, for its caption."""

    kind: str  # "all", "class" or "well"
    key: int
    joined: bool
    name: str = field(default="")

import math


def test_dl_basic_pooling(binary_studies):
    """DL pooling of 5 binary studies produces valid result."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl(
        yi=[s["yi"] for s in binary_studies],
        sei=[s["sei"] for s in binary_studies],
    )
    assert result["k"] == 5
    assert result["tau2"] >= 0
    assert result["i2"] >= 0 and result["i2"] <= 100
    assert result["ci_lower"] < result["pooled"] < result["ci_upper"]
    assert result["converged"] is True


def test_dl_homogeneous(homogeneous_studies):
    """Identical studies should give tau2 = 0, I2 = 0."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl(
        yi=[s["yi"] for s in homogeneous_studies],
        sei=[s["sei"] for s in homogeneous_studies],
    )
    assert abs(result["tau2"]) < 1e-10
    assert abs(result["i2"]) < 1e-10
    assert abs(result["pooled"] - math.log(0.80)) < 1e-10


def test_dl_single_study():
    """k=1: pooled = study effect, tau2 = 0."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl(yi=[math.log(0.75)], sei=[0.20])
    assert result["k"] == 1
    assert abs(result["pooled"] - math.log(0.75)) < 1e-10
    assert result["tau2"] == 0
    assert result["prediction_interval"] is None


def test_dl_two_studies():
    """k=2: tau2 can be computed, PI uses t-distribution with df=1."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl(yi=[math.log(0.5), math.log(1.5)], sei=[0.2, 0.2])
    assert result["k"] == 2
    assert result["tau2"] > 0
    assert result["prediction_interval"] is not None


def test_reml_basic(binary_studies):
    """REML pooling converges and gives similar result to DL."""
    from pipeline.meta_engine import pool_reml
    result = pool_reml(
        yi=[s["yi"] for s in binary_studies],
        sei=[s["sei"] for s in binary_studies],
    )
    assert result["k"] == 5
    assert result["converged"] is True
    assert result["tau2"] >= 0


def test_reml_homogeneous(homogeneous_studies):
    """REML on homogeneous data: tau2 ~ 0."""
    from pipeline.meta_engine import pool_reml
    result = pool_reml(
        yi=[s["yi"] for s in homogeneous_studies],
        sei=[s["sei"] for s in homogeneous_studies],
    )
    assert abs(result["tau2"]) < 1e-6


# Fixed heterogeneous reference dataset. The REML tau2 below was computed
# by directly maximizing the restricted log-likelihood
# l_R(tau2) = -0.5*sum(log(v_i+tau2)) - 0.5*log(sum w_i)
#             - 0.5*sum(w_i*(y_i-mu)^2)
# (scipy bounded minimize_scalar, xatol=1e-12) AND independently reproduced
# by the Fisher-scoring score 0.5*(sum w^2 r^2 - sum w + sum w^2 / sum w).
# The ML fixed point on the same data is 0.00141496, so this anchor also
# guards against silently shipping ML in place of REML.
_HET_YI = [0.10, 0.30, 0.35, 0.65, 0.45, 0.15]
_HET_SEI = [0.10, 0.12, 0.11, 0.30, 0.20, 0.09]
_HET_REML_TAU2 = 0.005678043561191636
_HET_ML_TAU2 = 0.001414960656512601


def test_reml_tau2_matches_reference():
    """REML tau2 matches the directly-optimized restricted-likelihood value."""
    from pipeline.meta_engine import pool_reml
    result = pool_reml(yi=_HET_YI, sei=_HET_SEI)
    assert result["converged"] is True
    assert abs(result["tau2"] - _HET_REML_TAU2) < 1e-6


def test_reml_is_not_ml_and_differs_from_dl():
    """REML tau2 must be distinct from both the ML fixed point and DL.

    Dropping the score's +sum(w^2)/sum(w) adjustment collapses REML onto the
    ML value (0.00141496); this guards against that regression. It also
    confirms REML and DL are genuinely different estimators on this data
    (their ordering is not universal, so we only assert they differ).
    """
    from pipeline.meta_engine import pool_dl, pool_reml
    reml = pool_reml(yi=_HET_YI, sei=_HET_SEI)
    dl = pool_dl(yi=_HET_YI, sei=_HET_SEI)
    # REML is materially larger than the ML value, not merely equal to it.
    assert reml["tau2"] - _HET_ML_TAU2 > 1e-4
    assert abs(reml["tau2"] - dl["tau2"]) > 1e-4


def test_reml_empty_input():
    """k=0: pool_reml returns a well-formed empty result."""
    from pipeline.meta_engine import pool_reml
    result = pool_reml(yi=[], sei=[])
    assert result["method"] == "REML"
    assert result["k"] == 0
    assert result["pooled"] is None
    assert result["tau2"] == 0.0


def test_reml_single_study():
    """k=1: pool_reml matches the trivial single-study case."""
    from pipeline.meta_engine import pool_reml
    result = pool_reml(yi=[math.log(0.75)], sei=[0.20])
    assert result["method"] == "REML"
    assert result["k"] == 1
    assert abs(result["pooled"] - math.log(0.75)) < 1e-10
    assert result["tau2"] == 0.0
    assert result["prediction_interval"] is None


def test_dl_c_zero_guard():
    """Guard for edge case with identical SE values."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl(yi=[0.1, 0.2, 0.3], sei=[0.5, 0.5, 0.5])
    assert result["tau2"] >= 0


def test_pool_convenience(binary_studies):
    """pool() convenience function runs both DL and REML."""
    from pipeline.meta_engine import pool
    dl, reml = pool(
        yi=[s["yi"] for s in binary_studies],
        sei=[s["sei"] for s in binary_studies],
    )
    assert dl["method"] == "DL"
    assert reml["method"] == "REML"

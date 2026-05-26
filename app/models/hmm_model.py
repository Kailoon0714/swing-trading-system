from __future__ import annotations

import pandas as pd
from hmmlearn.hmm import GaussianHMM


def fit_market_regime_model(features: pd.DataFrame, n_components: int = 3) -> GaussianHMM:
    model_features = features[["log_return", "rolling_volatility_14d", "momentum_score"]].dropna()
    if len(model_features) < n_components * 20:
        raise ValueError("Not enough observations to fit HMM regime model")

    model = GaussianHMM(n_components=n_components, covariance_type="full", n_iter=200, random_state=42)
    model.fit(model_features)
    return model

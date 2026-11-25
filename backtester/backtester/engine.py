"""Moteur de backtest."""

from __future__ import annotations

import pandas as pd


def positions_from_signal(signal: pd.Series) -> pd.Series:
    """Position réellement détenue chaque jour.

    Le signal du jour t n'est connu qu'à la clôture de t. On ne peut donc agir
    qu'ensuite : il détermine la position pendant le jour t + 1.
    Le décalage d'un jour (shift(1)) évite le biais d'anticipation
    (look-ahead bias), c'est-à-dire utiliser une information qu'on n'avait
    pas encore au moment de décider.
    """
    return signal.shift(1).fillna(0.0)


def run_backtest(prices: pd.Series, signal: pd.Series, cost: float = 0.001) -> pd.DataFrame:
    """Rejoue une stratégie jour après jour.

    prices : prix de clôture ajustés
    signal : 1 = investi, 0 = cash (calculé à la clôture de chaque jour)
    cost   : coût d'une transaction, en fraction du montant échangé
             (0.001 = 0,10 %, frais de courtage + écart achat/vente)

    Hypothèses : on achète et vend au prix de clôture ; le cash ne rapporte
    rien.

    Renvoie un tableau jour par jour : position, rendement de l'actif,
    rendement de la stratégie (frais déduits) et richesse (1 au départ).
    """
    asset_ret = prices.pct_change().fillna(0.0)
    position = positions_from_signal(signal.reindex(prices.index).fillna(0.0))

    # Volume échangé : de 0 à 1 (achat) ou de 1 à 0 (vente) -> 1.
    # Le changement de position décidé le soir t est exécuté à la clôture de t ;
    # on le compte dans le rendement du jour t + 1, première journée de la
    # nouvelle position.
    turnover = position.diff().abs().fillna(position.abs())
    strat_ret = position * asset_ret - turnover * cost

    return pd.DataFrame(
        {
            "position": position,
            "asset_return": asset_ret,
            "turnover": turnover,
            "strategy_return": strat_ret,
            "equity": (1 + strat_ret).cumprod(),
        }
    )

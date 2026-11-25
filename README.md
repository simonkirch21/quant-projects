# Projets de finance quantitative

Quatre projets construits pas à pas en Python, chacun testé et documenté. Le fil conducteur : **ne jamais croire un résultat sans l'avoir vérifié**.

| # | Projet | Ce qu'il montre | Tests |
|---|---|---|---|
| 1 | [Option pricer](option-pricer/) | Black-Scholes, grecques, volatilité implicite ; Monte Carlo avec réduction de variance (variance divisée par 24), options asiatiques | 40 |
| 2 | [Backtesting engine](backtester/) | Moteur sans biais d'anticipation, frais, Sharpe, drawdown ; démonstration du surapprentissage | 14 |
| 3 | [Modèle de risque](risk-model/) | VaR et Expected Shortfall par 4 méthodes, backtest de Kupiec, Christoffersen et feux de Bâle, contributions au risque | 19 |
| 4 | [Stratégie robuste](strategy/) | Walk-forward, sensibilité aux paramètres, bootstrap, Deflated Sharpe Ratio | 11 |

Données : prix ajustés quotidiens SPY, TLT et GLD de 2005 à 2024 (Yahoo Finance), enregistrés dans `backtester/data/` pour des résultats reproductibles.

```bash
pip install numpy scipy pandas matplotlib yfinance pytest
cd option-pricer && python -m pytest    # idem dans chaque dossier
```

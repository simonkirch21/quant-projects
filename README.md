<div align="center">

# Projets de finance quantitative

**Cinq projets en Python, du pricing au risque de marché et de crédit, testés et documentés.**

Fil conducteur : *ne jamais croire un résultat sans l'avoir vérifié.*

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-110%20réussis-2ea44f)
![Données](https://img.shields.io/badge/données-marchés%202005--2024%20·%2030%20000%20crédits-555)

</div>

---

## Les projets

| | Projet | Ce qu'il montre | Résultat clé | Tests |
|---|---|---|---|---|
| 1 | [**Pricer d'options**](option-pricer/) | Black-Scholes, grecques, volatilité implicite, Monte Carlo, options asiatiques | Variance du Monte Carlo divisée par **24** (européenne) et par **650** (asiatique) | 40 |
| 2 | [**Moteur de backtest**](backtester/) | Backtest sans biais d'anticipation, frais, Sharpe, drawdown | Oublier le décalage d'un jour transforme ×4,9 en **×34,7** | 14 |
| 3 | [**Risque de marché**](risk-model/) | VaR et ES par 5 méthodes (dont GARCH), backtest réglementaire, stress tests, VaR stressée et capital Bâle, valeurs extrêmes, [rapport de validation](risk-model/VALIDATION.md) | Pire stress : **2022** (−25 %), pas 2008 ; la loi normale sous-estime l'ES de **35 %** | 33 |
| 4 | [**Stratégie robuste**](strategy/) | Walk-forward, plateau de paramètres, bootstrap, Deflated Sharpe Ratio | La tendance ne résiste pas aux tests ; la diversification avec ciblage de volatilité, si | 11 |
| 5 | [**Risque de crédit**](credit-risk/) | Grille de score (WoE, IV, logistique), échelle de notation, perte attendue, capital Bâle IRB, VaR crédit Monte Carlo | Gini **0,53** ; perte prévue 13,8 % contre 14,4 % observée ; 7 classes validées sur le test | 12 |

---

### 1. Pricer d'options : Black-Scholes et Monte Carlo

<img src="option-pricer/figures/convergence.png" alt="Convergence du Monte Carlo" width="700">

Prix exact par la formule de Black-Scholes, puis par simulation. Le Monte Carlo converge vers le prix exact en $1/\sqrt{N}$ ; les variables antithétiques et la variable de contrôle divisent sa variance par 24 à coût égal. Pour l'option asiatique, qui n'a pas de formule, l'asiatique géométrique sert de variable de contrôle. → [Détails](option-pricer/)

### 2. Moteur de backtest

<img src="backtester/figures/equity_drawdown.png" alt="Richesse et drawdown" width="700">

20 ans de S&P 500. La moyenne mobile 200 jours rapporte moins que le marché (7,6 % contre 10,3 % par an), mais limite la pire chute à −22 % contre −55 %. Sur 499 paramétrages, le meilleur sur 2006-2014 ne prédit rien sur 2015-2024 : c'est le surapprentissage. → [Détails](backtester/)

### 3. Risque de marché : VaR, stress tests et validation

<img src="risk-model/figures/var_backtest.png" alt="Backtest de la VaR" width="700">

<img src="risk-model/figures/stress_tests.png" alt="Stress tests" width="700">

Portefeuille actions, obligations et or. Sur 18 ans, la VaR normale est dépassée 2,2 fois plus souvent que promis ; la simulation historique filtrée passe le test de Kupiec, et le GARCH à queues épaisses le test d'indépendance. Les stress tests montrent que 2022 a été pire que 2008 : actions et obligations ont chuté ensemble. Le projet calcule aussi la VaR stressée, le capital Bâle 2.5 et les quantiles extrêmes (EVT), et le modèle retenu fait l'objet d'un [rapport de validation](risk-model/VALIDATION.md) indépendant. → [Détails](risk-model/)

### 4. Stratégie multi-actifs robuste

<img src="strategy/figures/strategy.png" alt="Stratégie et sensibilité" width="700">

Tendance, ciblage de volatilité et diversification, démontés ingrédient par ingrédient. Le filtre de tendance est fragile (Sharpe de 0,39 à 0,84 selon la fenêtre) ; la diversification avec ciblage de volatilité forme un plateau (0,91 à 0,99), avec un Deflated Sharpe de 99,9 %. Son avance sur un simple portefeuille équipondéré n'est cependant pas statistiquement prouvée. → [Détails](strategy/)

### 5. Risque de crédit : de la grille de score au capital Bâle

<img src="credit-risk/figures/credit_risk.png" alt="Risque de crédit" width="700">

30 000 cartes de crédit réelles. Grille de score bancaire (Weight of Evidence, régression logistique, points), sans utiliser le sexe, la situation familiale ni l'âge ; échelle de 7 classes calibrée et validée sur des clients jamais vus ; perte attendue, capital Bâle IRB et VaR crédit à 99,9 % par Monte Carlo. Un gradient boosting sert de modèle challenger. → [Détails](credit-risk/)

---

## Lancer les projets

```bash
git clone https://github.com/simonkirch21/quant-projects.git
cd quant-projects
pip install numpy scipy pandas matplotlib yfinance scikit-learn pytest

cd option-pricer && python -m pytest && python scripts/demo.py
```

Même chose dans chaque dossier : `python -m pytest` lance les tests, `python scripts/demo.py` régénère les figures et les tableaux du README.

Données : prix ajustés quotidiens de SPY, TLT et GLD de 2005 à 2024 (Yahoo Finance), enregistrés dans `backtester/data/`, et 30 000 crédits à la consommation (UCI) dans `credit-risk/data/`, pour des résultats reproductibles.

<div align="center">
<sub>Projets réalisés pendant un Master 1 Finance · Voir aussi <a href="https://github.com/simonkirch21/analyse-actions">Analyse Actions</a>, application d'analyse boursière</sub>
</div>

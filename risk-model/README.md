# Modèle de risque : VaR et Expected Shortfall

Mesure et backtest du risque d'un portefeuille diversifié (60 % actions SPY, 30 % obligations longues TLT, 10 % or GLD) sur 2005-2024. Le projet compare 4 méthodes de VaR, les vérifie par des tests statistiques (Kupiec, Christoffersen, feux de Bâle) et décompose le risque par actif. Il est vérifié par 19 tests.

![Backtest de la VaR](figures/var_backtest.png)

## Les deux mesures

- **VaR 99 % à 1 jour** : la perte qu'on ne dépasse pas 99 jours sur 100.
- **Expected Shortfall (ES) 99 %** : la perte **moyenne** les 1 % de jours où l'on dépasse la VaR. Elle dit « quand ça va mal, ça va mal de combien ? ». C'est la mesure retenue par la réglementation bancaire actuelle (Bâle III / FRTB).

| Sur 20 ans | VaR 99 % | ES 99 % |
|---|---|---|
| Historique (les vrais pires jours) | 1,93 % | **2,84 %** |
| Loi normale (même moyenne, même volatilité) | 1,60 % | 1,84 % |

La loi normale sous-estime l'ES de **35 %**. Les krachs sont bien plus fréquents et violents que ne le prévoit la courbe en cloche : on parle de **queues épaisses**. Pire jour : −5,95 % le 12 mars 2020, soit 8,5 écarts-types : sous la loi normale, un tel jour arriverait moins d'une fois tous les 10¹⁴ ans.

## Les 4 méthodes de prévision

Chaque matin, on prévoit la VaR du jour **avec les seules données de la veille et avant**. Un test vérifie qu'aucune méthode ne regarde le futur.

| Méthode | Principe | Point fort | Point faible |
|---|---|---|---|
| **Historique 250 j** | Le 1 % des pires jours de la dernière année | Aucune hypothèse de loi | Réagit lentement, et estime mal un quantile extrême avec seulement 250 jours |
| **Normale 250 j** | Moyenne et écart-type de la dernière année, loi normale | Simple | Queues trop fines, réagit lentement |
| **Normale EWMA** | Volatilité où les jours récents pèsent plus, $\sigma_t^2 = \lambda\sigma_{t-1}^2 + (1-\lambda)r_{t-1}^2$, $\lambda = 0{,}94$ (RiskMetrics) | Réagit vite | Garde l'hypothèse normale |
| **Historique filtrée** | Rendements divisés par leur volatilité EWMA, quantile historique sur 500 j, puis multiplié par la volatilité prévue | Queues réelles **et** réaction rapide | Plus complexe |

## Backtest : la VaR a-t-elle tenu sa promesse ?

Du 29 décembre 2006 au 31 décembre 2024 (4 531 jours ; même période pour toutes les méthodes). Avec une VaR 99 %, on attend **45 dépassements**.

| Méthode | Dépassements | Taux | Kupiec p | Indépendance p | Pire fenêtre de 250 j | Temps en zone rouge |
|---|---|---|---|---|---|---|
| Historique 250 j | 65 | 1,43 % | 0,006 | < 0,001 | 13 (rouge) | 6 % |
| Normale 250 j | 101 | 2,23 % | < 0,001 | < 0,001 | 17 (rouge) | 19 % |
| Normale EWMA | 88 | 1,94 % | < 0,001 | 0,036 | 12 (rouge) | 5 % |
| **Historique filtrée** | **53** | **1,17 %** | **0,264** | 0,003 | **7 (orange)** | **0 %** |

- **Test de Kupiec** : le nombre de dépassements est-il compatible avec 1 % ? Une p-value inférieure à 5 % signifie que le modèle est rejeté. Seule l'historique filtrée passe.
- **Test de Christoffersen** : les dépassements sont-ils dispersés, ou arrivent-ils en grappes ? Tous les modèles sont rejetés : au début d'une crise, plusieurs dépassements s'enchaînent avant que le modèle s'adapte. L'EWMA et la filtrée sont les moins mauvaises.
- **Feux de Bâle** : sur 250 jours, 0 à 4 dépassements donnent le vert, 5 à 9 l'orange, 10 et plus le rouge (une banque en rouge voit son capital réglementaire augmenter). L'historique filtrée n'est jamais passée au rouge.

Le zoom 2020 montre la différence. La VaR normale 250 jours reste presque plate pendant le krach, parce qu'une année de calme pèse encore sur la moyenne. La filtrée s'adapte en quelques jours.

Dépassements par année :

| | 2008 | 2020 | 2022 |
|---|---|---|---|
| Historique 250 j | 13 | 8 | 7 |
| Normale 250 j | 16 | 9 | 16 |
| Normale EWMA | 5 | 11 | 8 |
| Historique filtrée | 3 | 6 | 1 |

> **Honnêteté méthodologique.** Les réglages de la méthode filtrée (λ = 0,94, fenêtre de 500 jours) ont été choisis après en avoir essayé 6, sur ces mêmes données. Son succès est donc en partie optimiste : c'est le surapprentissage mis en évidence dans le [projet 2](../backtester/). Les 3 autres méthodes utilisent leurs réglages standards, non optimisés.

## Erreur d'estimation

Même sur des données **parfaitement normales** (simulées), une VaR historique estimée sur 250 jours est dépassée environ **1,3 %** du temps au lieu de 1 %. Le 1 % des pires jours d'une année, c'est 2 ou 3 observations : l'estimation est bruitée, et ce bruit joue en moyenne dans le mauvais sens. Sur 1 000 jours, le taux revient à 1,08 %. Un test le vérifie.

## D'où vient le risque du portefeuille ?

La volatilité du portefeuille vaut $\sigma_p = \sqrt{w^\top \Sigma w}$. Chaque actif y contribue pour $w_i (\Sigma w)_i / \sigma_p$, et ces contributions s'additionnent exactement à $\sigma_p$ (théorème d'Euler).

| Actif | Poids | Volatilité journalière | Part du risque |
|---|---|---|---|
| SPY (actions) | 60 % | 1,20 % | **92 %** |
| TLT (obligations) | 30 % | 0,93 % | 4 % |
| GLD (or) | 10 % | 1,11 % | 4 % |

Avec 60 % du capital, les actions portent **92 % du risque**. Les obligations, corrélées négativement aux actions (−0,32), en compensent une partie. Un portefeuille « 60/40 » est en réalité un pari presque entièrement sur les actions. C'est le point de départ de l'allocation en **parité de risque**.

## Ce que vérifient les tests

- Valeurs de référence de la loi normale (VaR 2,326 σ, ES 2,665 σ).
- VaR et ES historiques = valeurs théoriques sur un grand échantillon normal.
- ES ≥ VaR.
- **Aucune prévision ne regarde le futur** : modifier le rendement du jour ne change pas la prévision du jour (pour les 4 méthodes).
- Sur données normales simulées : taux de dépassement plausible, test de Kupiec réussi avec un historique long, effet de l'erreur d'estimation à 250 jours.
- Test de Kupiec sur des cas connus ; test de Christoffersen qui détecte des grappes artificielles.
- Feux de Bâle.
- Les contributions au risque s'additionnent exactement à la VaR du portefeuille.

## Lancer le projet

Les prix sont ceux téléchargés par le [backtester](../backtester/) (`backtester/data/`).

```bash
pip install -r requirements.txt
python -m pytest          # 19 tests
python scripts/demo.py    # figure + tableaux
```

## Limites et pistes

- VaR à 1 jour. Le passage à 10 jours par la racine du temps (`scale_to_horizon`) suppose des jours indépendants, ce que contredisent les grappes de volatilité.
- Poids constants, rééquilibrés chaque jour.
- Pistes : modèle GARCH, loi de Student, VaR Monte Carlo multi-actifs, tests de stress sur scénarios historiques (2008, 2020).

# Rapport de validation : VaR 99 % à 1 jour par simulation historique filtrée

| | |
|---|---|
| **Modèle validé** | VaR 99 % à 1 jour, simulation historique filtrée (FHS), `rolling_var(..., method="fhs")` |
| **Portefeuille** | 60 % SPY (actions), 30 % TLT (obligations longues), 10 % GLD (or), rééquilibré chaque jour |
| **Usage prévu** | Mesure quotidienne du risque de marché, limites de risque, backtest réglementaire |
| **Type de revue** | Validation initiale, indépendante du développement |
| **Données** | Prix ajustés quotidiens Yahoo Finance, du 3 janvier 2005 au 31 décembre 2024 |
| **Chiffres reproductibles** | `python scripts/validation.py` |

> Exercice pédagogique. La structure suit celle des revues de modèles en banque : revue conceptuelle, données, implémentation, performance, constats classés par gravité, recommandations.

---

## 1. Synthèse

**Conclusion : modèle validé avec réserves.** Il peut être utilisé pour la mesure quotidienne du risque, sous réserve de la mise en œuvre des recommandations R1 et R2.

Points forts :
- le nombre de dépassements est conforme au niveau annoncé (53 pour 45 attendus, test de Kupiec p = 0,26), y compris sur chaque moitié de la période ;
- le modèle n'est jamais passé en zone rouge de Bâle en 18 ans, crises de 2008, 2020 et 2022 comprises ;
- l'implémentation a été reproduite de façon indépendante, à 10⁻¹⁷ près.

Constats :

| # | Constat | Gravité |
|---|---|---|
| F1 | Les dépassements arrivent en grappes (test de Christoffersen rejeté dans toutes les variantes) | **Élevée** |
| F2 | Le calibrage (λ = 0,94, fenêtre de 500 jours) a été choisi sur les données mêmes du backtest | Moyenne |
| F3 | La VaR descend trop bas en période calme : 6 dépassements en 2024, année peu volatile | Moyenne |
| F4 | Quand la VaR est dépassée, la perte la dépasse nettement (1,38 fois en moyenne) | Moyenne |
| F5 | Périmètre limité : 3 actifs, horizon 1 jour, risque mesuré au niveau du portefeuille | Faible |

---

## 2. Description du modèle

Pour prévoir la VaR du jour $t$ avec les seules données disponibles la veille :

1. **Volatilité EWMA** : $\sigma_t^2 = \lambda\,\sigma_{t-1}^2 + (1-\lambda)\,r_{t-1}^2$, avec $\lambda = 0{,}94$ (RiskMetrics).
2. **Rendements standardisés** : $z_s = r_s / \sigma_s$ pour les 500 jours précédant $t$.
3. **VaR** : $\text{VaR}_t = -\,q_{1\%}(z) \times \sigma_t$.

Le modèle combine la forme réelle des queues (quantile historique des $z$) et une réaction rapide aux changements de volatilité (EWMA).

## 3. Revue conceptuelle

| Hypothèse | Évaluation |
|---|---|
| Les rendements standardisés $z$ ont une loi stable dans le temps | Raisonnable : c'est l'objet même de la standardisation. Elle n'est pas parfaite : voir F1 et F3. |
| La volatilité EWMA est une bonne prévision de la volatilité du lendemain | Acceptable. L'EWMA n'a pas de retour à la moyenne : après un long calme, elle oublie le niveau habituel de volatilité (F3). Le GARCH, testé en challenger, corrige ce point. |
| 500 jours suffisent pour estimer un quantile à 1 % | Oui : 5 observations dans la queue. Avec 250 jours (2 ou 3 observations), l'erreur d'estimation biaise la VaR vers le bas ; c'est démontré par un test sur données simulées. |
| L'horizon de 1 jour peut être porté à 10 jours par la racine du temps | Vérifié empiriquement sur ce portefeuille : 6,11 % contre 6,01 % observé. À surveiller, car l'hypothèse de jours indépendants est contredite par F1. |

## 4. Données

- **Source** : Yahoo Finance, prix de clôture ajustés des dividendes et des divisions d'actions. Source gratuite, sans garantie de qualité : en banque, une source contractuelle (Bloomberg, Refinitiv) et des contrôles de qualité seraient exigés.
- **Contrôles réalisés** : séries complètes sur 5 033 jours communs aux trois actifs, aucune valeur manquante après alignement. Les extrêmes (−5,95 % le 12/03/2020) correspondent à des événements de marché réels.
- **Reproductibilité** : les données sont figées dans `backtester/data/` ; les résultats ne dépendent pas d'un nouveau téléchargement.

## 5. Revue de l'implémentation

| Contrôle | Résultat |
|---|---|
| **Réimplémentation indépendante** : VaR recalculée par une boucle simple, sans réutiliser le code du modèle, sur les 10 dernières dates | Écart maximal 3,5 × 10⁻¹⁸ : **conforme** |
| **Absence de regard vers le futur** : remplacer le rendement du jour $t$ par −50 % ne doit pas changer la VaR du jour $t$ | Test automatisé : **conforme** |
| **Comportement sur données simulées** : sur des rendements normaux, le taux de dépassement doit être proche de 1 % | Test automatisé : **conforme** |
| **Tests unitaires** | 33 tests réussis (`python -m pytest`) |

## 6. Performance

### 6.1 Backtest (3 janvier 2007 → 31 décembre 2024, 4 530 jours)

| Indicateur | Résultat | Seuil | Verdict |
|---|---|---|---|
| Dépassements | 53 pour 45 attendus (1,17 %) | | |
| Test de Kupiec | p = 0,263 | > 5 % | ✅ |
| Test de Christoffersen | p = 0,003 | > 5 % | ❌ (F1) |
| Pire fenêtre de 250 jours | 7 dépassements | rouge à partir de 10 | 🟠 |
| Temps passé en zone rouge | 0 % | | ✅ |

### 6.2 Stabilité dans le temps

| Période | Dépassements | Attendus | Kupiec p | Indépendance p | Pire fenêtre de 250 j |
|---|---|---|---|---|---|
| 2007-2015 | 28 | 23 | 0,277 | 0,048 | 5 |
| 2016-2024 | 25 | 23 | 0,624 | 0,030 | 7 |

Le nombre de dépassements est stable sur les deux moitiés, et le problème de grappes aussi.

Dépassements par année : 2007 : 5 · 2008 : 3 · 2009 : 0 · 2010 : 4 · 2011 : 3 · 2012 : 3 · 2013 : 4 · 2014 : 2 · 2015 : 4 · 2016 : 2 · 2017 : 1 · 2018 : 4 · 2019 : 2 · 2020 : 6 · 2021 : 2 · 2022 : 1 · 2023 : 1 · **2024 : 6**.

### 6.3 Sensibilité au calibrage (période commune 2009-2024, 40 dépassements attendus)

| λ | Fenêtre | Dépassements | Kupiec p | Indépendance p | Pire fenêtre de 250 j |
|---|---|---|---|---|---|
| 0,94 | 250 | 56 | 0,019 ❌ | 0,001 | 8 |
| **0,94** | **500** | **45** | **0,461** | 0,001 | 7 |
| 0,94 | 1 000 | 43 | 0,668 | 0,011 | 8 |
| 0,97 | 250 | 61 | 0,002 ❌ | 0,015 | 9 |
| 0,97 | 500 | 45 | 0,461 | 0,001 | 6 |
| 0,97 | 1 000 | 42 | 0,784 | 0,000 | 7 |

Le résultat dépend peu de λ, et il est stable pour toute fenêtre d'au moins 500 jours : c'est un **plateau**, pas un réglage chanceux. Une fenêtre de 250 jours est trop courte, ce qui confirme l'erreur d'estimation décrite en section 3.

### 6.4 Comparaison aux modèles concurrents (challengers)

| Modèle | Dépassements | Kupiec p | Indépendance p | Pire fenêtre de 250 j |
|---|---|---|---|---|
| **Historique filtrée (modèle validé)** | 53 | **0,263** | 0,003 | **7** |
| GARCH(1,1) Student | 69 | 0,001 | **0,113** | 10 |
| Normale EWMA | 88 | < 0,001 | 0,036 | 12 |
| Historique 250 jours | 65 | 0,006 | < 0,001 | 13 |
| Normale 250 jours | 101 | < 0,001 | < 0,001 | 17 |

Le modèle validé est le meilleur sur le nombre de dépassements et sur les feux de Bâle. Le GARCH est le seul à passer le test d'indépendance : ses qualités sont complémentaires (voir R1).

## 7. Constats détaillés

**F1 : dépassements en grappes (gravité élevée).** Le test de Christoffersen est rejeté sur toute la période, sur chaque moitié et pour toutes les variantes de calibrage. 8 des 53 dépassements sont suivis d'un autre dans les 5 jours. Au début d'une crise, l'EWMA réagit avec un jour de retard. Le défaut est structurel, et un changement de réglage ne le corrige pas. Conséquence : la règle de la racine du temps, qui suppose des jours indépendants, peut sous-estimer le risque à 10 jours en début de crise.

**F2 : calibrage choisi sur les données de test (gravité moyenne).** λ = 0,94 et 500 jours ont été retenus après l'essai de 6 combinaisons sur la période même du backtest. Le risque de surapprentissage est atténué par l'analyse de sensibilité (6.3), qui montre un plateau, et par la stabilité sur les deux moitiés de la période (6.2). Il n'est pas éliminé, faute de données réellement hors échantillon.

**F3 : VaR trop basse en période calme (gravité moyenne).** En 2024, année peu volatile, la VaR est descendue vers 1,0 % - 1,2 %, et 6 pertes modérées (de −1,28 % à −2,36 %) l'ont dépassée. Le même schéma apparaît avant le choc de février 2018. L'EWMA « oublie » vite le niveau habituel de volatilité.

**F4 : ampleur des dépassements (gravité moyenne).** Les jours de dépassement, la perte vaut en moyenne 1,38 fois la VaR, contre 1,15 attendu sous une loi normale ; au maximum 2,75 fois (27/02/2007). La VaR ne dit rien de cette ampleur. L'ES 97,5 % et les estimations par valeurs extrêmes (ξ = 0,20) doivent donc compléter la VaR.

**F5 : périmètre (gravité faible).** Le modèle mesure le risque au niveau du portefeuille agrégé : il ne décompose pas par facteur de risque et ne s'adapte pas automatiquement à un changement de composition. Il n'intègre ni le risque de liquidité ni les horizons de liquidité de la FRTB.

## 8. Recommandations

| # | Recommandation | Constats traités | Priorité |
|---|---|---|---|
| R1 | Remplacer l'EWMA par une volatilité GARCH dans la standardisation (« FHS-GARCH ») : retour à la moyenne en période calme et réaction plus marquée aux chocs, en gardant le quantile historique | F1, F3 | Haute |
| R2 | Introduire un plancher : VaR ≥ 80 % de la VaR historique sur 3 ans | F3 | Haute |
| R3 | Publier l'ES 97,5 % et l'ES par valeurs extrêmes à côté de la VaR dans le reporting quotidien | F4 | Moyenne |
| R4 | Revalider le calibrage chaque année sur l'année écoulée, qui sera alors réellement hors échantillon | F2 | Moyenne |
| R5 | Mesurer la VaR par facteur de risque (actions, taux, or) pour les changements de composition, et compléter par les stress tests | F5 | Faible |

## 9. Conclusion

Le modèle est **conceptuellement solide, correctement implémenté et performant** sur le critère principal du régulateur, le nombre de dépassements. Ses faiblesses sont connues, mesurées et liées entre elles : réaction tardive aux chocs, sous-estimation en période calme, perte au-delà de la VaR. Il est **validé avec réserves**. Une revue de suivi est à prévoir après la mise en œuvre de R1 et R2.

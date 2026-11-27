# Guide des postes : comment remplir `template.csv`

Une ligne par société et par année. Montants en **millions d'euros**, tels que publiés dans le rapport annuel de l'année (pas les chiffres retraités plus tard). Il faut **au moins deux années consécutives** pour calculer le M-Score, les accruals et les variations.

| Colonne | Poste | Où le trouver | Remarques |
|---|---|---|---|
| `company`, `year` | Société, exercice | | |
| `revenue` | Chiffre d'affaires | Compte de résultat | Pour un prestataire de paiement : chiffre d'affaires **brut**, commissions d'interchange comprises, comme publié |
| `cost_of_sales` | Coût des ventes | Compte de résultat | Compte « par nature » (Wirecard) : coût des matières (*cost of materials*). Adyen : coûts facturés par les institutions financières + coût des stocks |
| `sga` | Frais commerciaux, généraux et administratifs | Compte de résultat | Compte « par nature » : charges de personnel + autres charges d'exploitation |
| `depreciation` | Dotations aux amortissements | Compte de résultat ou tableau de flux | Total des amortissements (y compris ceux des actifs acquis) |
| `ebit` | Résultat d'exploitation | Compte de résultat | EBIT publié, pas l'EBIT « ajusté » |
| `net_income` | Résultat net | Compte de résultat | Résultat après impôt |
| `cfo` | Flux de trésorerie d'exploitation | Tableau des flux de trésorerie | Ligne publiée « Cash flow from operating activities » |
| `cfo_adjusted` | Flux d'exploitation « ajusté » | Tableau complémentaire | Facultatif. Wirecard publiait un flux « ajusté » qui exclut les éléments jugés transitoires |
| `receivables` | Créances | Bilan, actif courant | Créances clients **+ créances de l'activité d'acquisition** (Wirecard) ou **sur les commerçants et institutions financières** (Adyen) |
| `receivables_acquiring` | dont créances de l'activité d'acquisition | Bilan | Facultatif, pour information |
| `current_assets` | Actif courant | Bilan | Total |
| `ppe` | Immobilisations corporelles | Bilan | Hors droits d'utilisation (IFRS 16) |
| `securities` | Titres et placements non courants | Bilan | Actifs financiers non courants + titres mis en équivalence. Sert à l'indice AQI |
| `total_assets` | Total de l'actif | Bilan | |
| `current_liabilities` | Passif courant | Bilan | Total |
| `long_term_debt` | Dettes financières non courantes | Bilan | Y compris les dettes locatives non courantes |
| `interest_bearing_debt` | Dettes financières portant intérêt | Bilan | Non courantes + courantes |
| `total_liabilities` | Total des dettes | Bilan | Doit vérifier : actif = dettes + capitaux propres |
| `equity` | Capitaux propres | Bilan | Total |
| `retained_earnings` | Réserves (bénéfices non distribués) | Bilan | |
| `cash` | Trésorerie et équivalents | Bilan | |
| `market_cap` | Capitalisation boursière au 31 décembre | Section « l'action » du rapport, ou cours × nombre d'actions | Facultatif : seulement pour le Z-Score d'origine. Vide si la société n'est pas cotée |
| `source` | Fichier du rapport | | |
| `pages` | Pages du PDF utilisées | | Numéros de page **du fichier PDF** (BS = bilan, IS = compte de résultat, CF = flux de trésorerie) |

`python -m redflags analyze` contrôle les données avant tout calcul : postes manquants, actif ≠ passif + capitaux propres, sous-totaux incohérents.

Utilisateurs principaux

Gérant



Le gérant souhaite disposer d’une vue globale sur les ventes, le stock et les risques financiers.



Responsable des achats



Le responsable des achats souhaite savoir quels produits commander et en quelle quantité.



Responsable de stock



Le responsable de stock souhaite détecter les ruptures, le surstock et les produits inactifs.



Analyste ou administrateur



L’analyste souhaite contrôler les données, les pipelines et les performances des modèles.



User stories prioritaires

US-01 — Importer les ventes



En tant que responsable de stock, je veux importer mon historique de ventes depuis un fichier CSV ou Excel afin d’analyser les performances de mes produits.



Critères d’acceptation

Le système accepte un fichier valide.

Le système vérifie les colonnes obligatoires.

Le système indique les lignes incorrectes.

Les données valides sont enregistrées dans PostgreSQL.

US-02 — Consulter les indicateurs



En tant que gérant, je veux consulter les principaux indicateurs de vente et de stock afin de comprendre rapidement la situation de mon entreprise.



Critères d’acceptation

Le chiffre d’affaires est affiché.

La marge estimée est affichée.

La valeur du stock est affichée.

Les produits en rupture sont identifiés.

Les filtres par période et magasin sont disponibles.

US-03 — Prévoir la demande



En tant que responsable des achats, je veux connaître la demande prévue pour chaque produit afin de planifier mes futures commandes.



Critères d’acceptation

Une prévision est disponible pour chaque produit éligible.

Les horizons de 7, 30 et 90 jours sont proposés.

Les résultats sont représentés dans un graphique.

La date de génération de la prévision est affichée.

US-04 — Identifier les risques de rupture



En tant que responsable de stock, je veux identifier les produits qui risquent une rupture afin d’agir avant l’épuisement du stock.



Critères d’acceptation

Le système compare le stock disponible à la demande prévue.

Un niveau de risque est attribué.

Les produits critiques sont affichés en premier.

Le nombre estimé de jours avant rupture est fourni.

US-05 — Identifier le surstock



En tant que gérant, je veux identifier les produits en surstock afin de réduire le capital immobilisé.



Critères d’acceptation

Les produits possédant une couverture excessive sont identifiés.

La valeur estimée du surstock est calculée.

Les produits concernés peuvent être filtrés par catégorie.

Le système indique depuis combien de temps le produit se vend lentement.

US-06 — Obtenir une recommandation



En tant que responsable des achats, je veux connaître la quantité recommandée à commander afin de réduire les ruptures et le surstock.



Critères d’acceptation

La quantité recommandée est calculée.

Le délai fournisseur est pris en compte.

Le stock de sécurité est pris en compte.

Les commandes déjà en cours sont prises en compte.

La recommandation est accompagnée d’une justification.

US-07 — Contrôler les performances du modèle



En tant qu’analyste, je veux consulter les performances des modèles afin de vérifier la fiabilité des prévisions.



Critères d’acceptation

Le modèle utilisé est affiché.

Les principales métriques sont visibles.

Les performances sont comparées à une baseline.

La version du modèle est identifiable.


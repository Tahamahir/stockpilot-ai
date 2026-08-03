Périmètre du MVP

Objectif du MVP



Le MVP doit démontrer qu’une entreprise peut importer ses données de vente et de stock, puis recevoir des analyses, des prévisions et des recommandations de réapprovisionnement.



Fonctionnalités incluses

Importation des données



L’utilisateur peut importer :



un catalogue de produits ;

un historique de ventes ;

un état actuel du stock ;

des informations sur les magasins ;

des informations sur les fournisseurs.



Les formats initiaux acceptés sont CSV et Excel.



Validation des données



Le système doit détecter :



les colonnes manquantes ;

les formats de date incorrects ;

les valeurs manquantes ;

les doublons ;

les quantités invalides ;

les prix négatifs ;

les produits inconnus ;

les lignes qui ne peuvent pas être importées.

Analyse descriptive



Le tableau de bord doit afficher :



le chiffre d’affaires ;

la marge brute estimée ;

les quantités vendues ;

les produits les plus vendus ;

les produits les moins vendus ;

les ventes par catégorie ;

les ventes par magasin ;

la valeur du stock ;

les produits en rupture ;

les produits en surstock.

Prévision de la demande



La plateforme doit produire des prévisions pour :



les sept prochains jours ;

les trente prochains jours ;

les quatre-vingt-dix prochains jours.



Les prévisions doivent être disponibles par produit et par magasin.



Optimisation du stock



Pour chaque produit, le système doit calculer :



la position de stock ;

la demande estimée pendant le délai fournisseur ;

le stock de sécurité ;

le point de commande ;

la quantité de réapprovisionnement recommandée ;

le niveau de risque.

Dashboard



Le MVP doit contenir les pages suivantes :



Vue générale

Analyse des ventes

État du stock

Prévisions

Recommandations

Importation des données

Performance des modèles

Suivi des modèles



Les expériences de Machine Learning doivent enregistrer :



le nom du modèle ;

les paramètres ;

les métriques ;

la période d’entraînement ;

les artefacts ;

la version du modèle.

Fonctionnalités exclues du MVP



Les éléments suivants seront développés après validation du produit :



paiement en ligne ;

gestion complète des abonnements ;

application mobile ;

notifications WhatsApp ;

prévisions en temps réel ;

connexion automatique aux ERP ;

connexion aux logiciels de caisse ;

optimisation avancée sous contrainte budgétaire ;

architecture Kubernetes ;

microservices complexes ;

gestion complète de plusieurs entreprises ;

chatbot exécutant librement du SQL.

Critères de réussite du MVP



Le MVP sera considéré comme fonctionnel lorsqu’un utilisateur pourra :



importer ses fichiers ;

voir si les données sont valides ;

consulter ses indicateurs ;

visualiser les prévisions ;

identifier les risques de rupture ;

obtenir une quantité recommandée ;

comprendre la raison de la recommandation.


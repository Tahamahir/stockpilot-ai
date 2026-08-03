\# Architecture de StockPilot AI



\## 1. Objectif de l’architecture



StockPilot AI est une plateforme end-to-end permettant de collecter, transformer et analyser les données de ventes et de stock afin de :



\* prévoir la demande future ;

\* détecter les risques de rupture ;

\* identifier les situations de surstock ;

\* recommander les quantités à commander ;

\* présenter les résultats dans une interface simple ;

\* expliquer les recommandations en langage naturel.



L’architecture doit être :



\* reproductible ;

\* modulaire ;

\* conteneurisée ;

\* testable ;

\* évolutive ;

\* simple à lancer localement.



\---



\## 2. Architecture générale



```text

Fichiers CSV / Excel / APIs

&#x20;            |

&#x20;            v

&#x20;     Apache Airflow

&#x20;Ingestion et orchestration

&#x20;            |

&#x20;            v

&#x20;       PostgreSQL

&#x20;Stockage des données brutes

&#x20;            |

&#x20;            v

&#x20;           dbt

&#x20;Nettoyage et transformation

&#x20;            |

&#x20;            v

&#x20;  Tables analytiques et ML

&#x20;            |

&#x20;     +------+------+

&#x20;     |             |

&#x20;     v             v

Machine Learning   Dashboard

&#x20;     |             |

&#x20;     v             |

&#x20;   MLflow          |

&#x20;     |             |

&#x20;     v             |

&#x20;  FastAPI <--------+

&#x20;     |

&#x20;     +----------------+

&#x20;     |                |

&#x20;     v                v

&#x20; Streamlit         Ollama

&#x20; Interface         Assistant IA

```



\---



\## 3. Flux des données



\### Étape 1 — Importation



L’utilisateur importe les données suivantes :



\* catalogue des produits ;

\* historique des ventes ;

\* état du stock ;

\* informations sur les magasins ;

\* fournisseurs ;

\* commandes fournisseurs ;

\* promotions.



Les premiers formats acceptés seront :



\* CSV ;

\* Excel.



À long terme, la plateforme pourra également se connecter à :



\* des logiciels de caisse ;

\* des ERP ;

\* des plateformes e-commerce ;

\* des APIs externes.



\---



\### Étape 2 — Orchestration avec Apache Airflow



Apache Airflow sera utilisé pour planifier et superviser les pipelines.



Airflow devra :



\* détecter les nouveaux fichiers ;

\* vérifier leur présence ;

\* lancer les contrôles de qualité ;

\* charger les données dans PostgreSQL ;

\* exécuter les transformations dbt ;

\* lancer l’entraînement des modèles ;

\* générer les prévisions ;

\* calculer les recommandations ;

\* enregistrer le statut de chaque pipeline.



Exemples de DAGs :



```text

dag\_ingest\_retail\_data

dag\_validate\_data

dag\_dbt\_transformations

dag\_train\_forecasting\_models

dag\_generate\_forecasts

dag\_generate\_recommendations

dag\_monitor\_model\_performance

```



\---



\### Étape 3 — Stockage dans PostgreSQL



PostgreSQL sera utilisé comme base de données principale.



Les données seront organisées dans plusieurs schémas :



```text

raw

staging

intermediate

analytics

ml

```



\#### Schéma `raw`



Contient les données telles qu’elles sont importées.



Exemples :



```text

raw.sales

raw.products

raw.inventory

raw.suppliers

raw.purchase\_orders

```



\#### Schéma `staging`



Contient les données nettoyées et standardisées par dbt.



\#### Schéma `intermediate`



Contient les transformations intermédiaires nécessaires aux analyses.



\#### Schéma `analytics`



Contient les tables finales utilisées par le dashboard et les rapports.



\#### Schéma `ml`



Contient :



\* les features ;

\* les prévisions ;

\* les scores de risque ;

\* les recommandations ;

\* les performances des modèles.



\---



\### Étape 4 — Transformation avec dbt



dbt sera utilisé pour transformer les données SQL.



Les principales responsabilités de dbt seront :



\* renommer les colonnes ;

\* corriger les types ;

\* supprimer ou signaler les doublons ;

\* gérer les valeurs manquantes ;

\* créer les tables analytiques ;

\* calculer les indicateurs métier ;

\* exécuter les tests de qualité ;

\* générer la documentation ;

\* afficher la lineage des données.



Organisation prévue :



```text

dbt/models/

├── staging/

├── intermediate/

└── marts/

```



Exemples de modèles :



```text

stg\_sales

stg\_products

stg\_inventory

int\_daily\_product\_sales

int\_product\_profitability

fct\_sales\_daily

fct\_inventory\_daily

mart\_inventory\_health

mart\_demand\_features

mart\_reorder\_recommendations

```



\---



\## 4. Couche Machine Learning



La couche Machine Learning sera responsable de la prévision de la demande.



\### Entrées du modèle



Les modèles pourront utiliser :



\* l’historique des ventes ;

\* le jour de la semaine ;

\* le mois ;

\* la saison ;

\* le prix ;

\* les promotions ;

\* le magasin ;

\* la catégorie du produit ;

\* le délai fournisseur ;

\* les ventes précédentes ;

\* les moyennes mobiles ;

\* la disponibilité du stock.



\### Modèles à comparer



Les premiers modèles seront :



\* prévision naïve ;

\* moyenne mobile ;

\* Holt-Winters ;

\* Random Forest ;

\* HistGradientBoosting ;

\* XGBoost ou LightGBM.



\### Sorties du modèle



Pour chaque produit et magasin :



\* prévision à 7 jours ;

\* prévision à 30 jours ;

\* prévision à 90 jours ;

\* intervalle ou niveau d’incertitude ;

\* date de génération ;

\* version du modèle utilisé.



\---



\## 5. Suivi des modèles avec MLflow



MLflow sera utilisé pour suivre les expériences de Machine Learning.



MLflow enregistrera :



\* le nom du modèle ;

\* les paramètres ;

\* les hyperparamètres ;

\* les métriques ;

\* les variables utilisées ;

\* la période d’entraînement ;

\* les graphiques ;

\* le modèle entraîné ;

\* la version du code Git ;

\* la version du dataset.



Les modèles pourront recevoir les statuts suivants :



```text

candidate

challenger

champion

```



Le modèle `champion` sera utilisé pour produire les prévisions en production.



\---



\## 6. Calcul des recommandations de stock



Les recommandations seront calculées à partir des prévisions et de l’état actuel du stock.



\### Position de stock



```text

inventory\_position =

stock\_on\_hand

\+ quantity\_on\_order

\- backorders

```



\### Point de commande



```text

reorder\_point =

forecast\_during\_lead\_time

\+ safety\_stock

```



\### Quantité recommandée



```text

recommended\_quantity =

max(

&#x20;   0,

&#x20;   target\_stock\_level - inventory\_position

)

```



Le calcul devra également prendre en compte :



\* la quantité minimale de commande ;

\* la taille des colis ;

\* le délai fournisseur ;

\* les commandes déjà en cours ;

\* le niveau de service souhaité ;

\* le stock de sécurité.



\---



\## 7. API avec FastAPI



FastAPI servira de couche de communication entre :



\* PostgreSQL ;

\* les modèles Machine Learning ;

\* Streamlit ;

\* Ollama ;

\* les futurs clients externes.



Endpoints prévus :



```text

GET  /health

GET  /products

GET  /sales/summary

GET  /inventory/alerts

GET  /forecasts

GET  /recommendations

POST /data/upload

POST /models/train

GET  /models/status

```



FastAPI permettra de séparer la logique métier de l’interface utilisateur.



\---



\## 8. Interface avec Streamlit



Streamlit sera utilisé pour créer le dashboard du MVP.



Pages prévues :



```text

1\. Vue générale

2\. Analyse des ventes

3\. État du stock

4\. Prévisions

5\. Recommandations

6\. Importation des données

7\. Performance des modèles

8\. Assistant IA

```



L’interface permettra de filtrer les résultats par :



\* période ;

\* magasin ;

\* produit ;

\* catégorie ;

\* fournisseur ;

\* niveau de risque.



\---



\## 9. Assistant avec Ollama



Ollama sera utilisé pour proposer un assistant local.



L’utilisateur pourra poser des questions comme :



\* Quels produits risquent une rupture cette semaine ?

\* Quels produits sont actuellement en surstock ?

\* Quels produits dois-je commander aujourd’hui ?

\* Pourquoi les ventes ont-elles diminué ?

\* Résume les performances du magasin.



Ollama ne devra pas calculer directement les indicateurs.



Le fonctionnement prévu est :



```text

Question utilisateur

&#x20;       |

&#x20;       v

Identification de l’intention

&#x20;       |

&#x20;       v

Appel d’une fonction métier autorisée

&#x20;       |

&#x20;       v

Lecture des résultats PostgreSQL

&#x20;       |

&#x20;       v

Génération d’une explication

```



Les fonctions autorisées pourront être :



```text

get\_stockout\_risks()

get\_overstock\_products()

get\_sales\_summary()

get\_product\_forecast()

get\_reorder\_recommendations()

```



Cette approche réduit les risques d’hallucination et d’exécution de requêtes SQL dangereuses.



\---



\## 10. Conteneurisation avec Docker



Tous les services seront exécutés dans des conteneurs Docker.



Services prévus :



```text

postgres

airflow-webserver

airflow-scheduler

dbt

mlflow

fastapi

streamlit

ollama

minio

```



MinIO restera optionnel pour la première version.



L’objectif est de pouvoir démarrer le projet avec :



```bash

docker compose up --build

```



\---



\## 11. Versionnement avec Git



Git et GitHub seront utilisés pour :



\* versionner le code ;

\* suivre les modifications ;

\* créer des branches ;

\* gérer les issues ;

\* documenter les fonctionnalités ;

\* automatiser les tests ;

\* présenter le projet aux recruteurs.



Branches principales :



```text

main

develop

```



Exemples de branches fonctionnelles :



```text

feature/data-generation

feature/airflow-ingestion

feature/dbt-models

feature/demand-forecasting

feature/streamlit-dashboard

```



\---



\## 12. CI/CD avec GitHub Actions



À chaque pull request, GitHub Actions devra vérifier :



\* la qualité du code Python ;

\* les tests unitaires ;

\* les tests dbt ;

\* la construction des images Docker ;

\* le fonctionnement de FastAPI ;

\* l’absence de secrets dans le repository.



Pipeline prévu :



```text

Push ou Pull Request

&#x20;       |

&#x20;       v

Lint du code

&#x20;       |

&#x20;       v

Tests unitaires

&#x20;       |

&#x20;       v

Tests dbt

&#x20;       |

&#x20;       v

Construction Docker

&#x20;       |

&#x20;       v

Validation finale

```



\---



\## 13. Sécurité



Les règles minimales de sécurité seront :



\* ne jamais publier le fichier `.env` ;

\* ne jamais enregistrer de mots de passe dans Git ;

\* utiliser des requêtes SQL paramétrées ;

\* valider les fichiers importés ;

\* limiter la taille des fichiers ;

\* filtrer les données avec `tenant\_id` ;

\* limiter les actions disponibles pour Ollama ;

\* journaliser les erreurs importantes.



\---



\## 14. Architecture du MVP



Pour la première version, le projet utilisera une architecture simple et centralisée :



```text

Un repository GitHub

Un fichier Docker Compose

Une base PostgreSQL

Des DAGs Airflow

Un projet dbt

Un module Machine Learning

Un serveur MLflow

Une API FastAPI

Une interface Streamlit

Un service Ollama

```



Le projet n’utilisera pas encore :



\* Kubernetes ;

\* Kafka ;

\* architecture temps réel ;

\* multiples microservices ;

\* infrastructure cloud complexe.



\---



\## 15. Évolution vers un SaaS



Après validation du MVP, l’architecture pourra évoluer pour intégrer :



\* plusieurs entreprises ;

\* authentification ;

\* gestion des rôles ;

\* abonnements ;

\* paiement en ligne ;

\* notifications ;

\* stockage cloud ;

\* connexions ERP ;

\* surveillance avancée ;

\* déploiement automatique.



L’ajout de `tenant\_id` dès le début permettra de préparer cette évolution.



\---



\## 16. Flux complet cible



```text

1\. L’utilisateur importe ses fichiers.



2\. Airflow valide et charge les données.



3\. PostgreSQL conserve les données brutes.



4\. dbt nettoie et transforme les données.



5\. Le module ML crée les features.



6\. Les modèles sont entraînés et comparés.



7\. MLflow enregistre les expériences.



8\. Le meilleur modèle génère les prévisions.



9\. Le moteur de stock calcule les recommandations.



10\. FastAPI expose les résultats.



11\. Streamlit affiche les tableaux de bord.



12\. Ollama explique les résultats à l’utilisateur.

```




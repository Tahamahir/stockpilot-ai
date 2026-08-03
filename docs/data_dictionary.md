Dictionnaire de données initial

Table companies

Colonne	Type	Description

tenant\_id	UUID	Identifiant unique de l’entreprise

company\_name	VARCHAR	Nom de l’entreprise

industry	VARCHAR	Secteur d’activité

country	VARCHAR	Pays

created\_at	TIMESTAMP	Date de création

Table stores

Colonne	Type	Description

store\_id	VARCHAR	Identifiant du magasin

tenant\_id	UUID	Identifiant de l’entreprise

store\_name	VARCHAR	Nom du magasin

city	VARCHAR	Ville

region	VARCHAR	Région

active	BOOLEAN	Statut du magasin

Table categories

Colonne	Type	Description

category\_id	VARCHAR	Identifiant de la catégorie

tenant\_id	UUID	Identifiant de l’entreprise

category\_name	VARCHAR	Nom de la catégorie

Table products

Colonne	Type	Description

product\_id	VARCHAR	Identifiant du produit

tenant\_id	UUID	Identifiant de l’entreprise

product\_name	VARCHAR	Nom du produit

category\_id	VARCHAR	Catégorie du produit

supplier\_id	VARCHAR	Fournisseur principal

purchase\_price	NUMERIC	Prix d’achat

selling\_price	NUMERIC	Prix de vente

lead\_time\_days	INTEGER	Délai fournisseur

minimum\_order\_quantity	INTEGER	Quantité minimale

package\_size	INTEGER	Nombre d’unités par colis

active	BOOLEAN	Statut du produit

Table sales

Colonne	Type	Description

sale\_id	VARCHAR	Identifiant de la vente

tenant\_id	UUID	Identifiant de l’entreprise

sale\_date	DATE	Date de la vente

store\_id	VARCHAR	Magasin

product\_id	VARCHAR	Produit vendu

quantity	INTEGER	Quantité vendue

unit\_price	NUMERIC	Prix unitaire

discount	NUMERIC	Remise appliquée

total\_amount	NUMERIC	Montant de la vente

Table inventory

Colonne	Type	Description

inventory\_date	DATE	Date du relevé

tenant\_id	UUID	Identifiant de l’entreprise

store\_id	VARCHAR	Magasin

product\_id	VARCHAR	Produit

stock\_on\_hand	INTEGER	Stock physiquement disponible

quantity\_on\_order	INTEGER	Quantité déjà commandée

backorders	INTEGER	Commandes clients en attente

Table suppliers

Colonne	Type	Description

supplier\_id	VARCHAR	Identifiant du fournisseur

tenant\_id	UUID	Identifiant de l’entreprise

supplier\_name	VARCHAR	Nom du fournisseur

average\_lead\_time	INTEGER	Délai moyen de livraison

minimum\_order\_value	NUMERIC	Valeur minimale de commande

active	BOOLEAN	Statut du fournisseur

Table promotions

Colonne	Type	Description

promotion\_id	VARCHAR	Identifiant de la promotion

tenant\_id	UUID	Identifiant de l’entreprise

product\_id	VARCHAR	Produit concerné

store\_id	VARCHAR	Magasin concerné

start\_date	DATE	Début de la promotion

end\_date	DATE	Fin de la promotion

discount\_percentage	NUMERIC	Pourcentage de remise

Table purchase\_orders

Colonne	Type	Description

purchase\_order\_id	VARCHAR	Identifiant de la commande

tenant\_id	UUID	Identifiant de l’entreprise

supplier\_id	VARCHAR	Fournisseur

product\_id	VARCHAR	Produit commandé

order\_date	DATE	Date de commande

expected\_delivery\_date	DATE	Livraison prévue

actual\_delivery\_date	DATE	Livraison réelle

ordered\_quantity	INTEGER	Quantité commandée

received\_quantity	INTEGER	Quantité reçue

status	VARCHAR	Statut de la commande


import pandas as pd

# Lecture des données
my_avis_film_df = pd.read_csv('data/avis_film_fr_sample.csv', sep=';')

# affichage d'un échantillon
print(my_avis_film_df.head(5))
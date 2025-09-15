import matplotlib.pyplot as plt
import matplotlib.image as img

# Lecture du fichier
my_first_car = img.imread("data/cars_detection/car425.jpg")

# Affichage de l'image
plt.imshow(my_first_car)
plt.show()
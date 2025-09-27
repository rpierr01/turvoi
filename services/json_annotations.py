import os
import json
from datetime import datetime
from typing import List, Dict, Optional

# Configuration
DATA_DIR = "data"
IMAGES_DIR = os.path.join(DATA_DIR, "cars_detection")
ANNOTATIONS_JSON = os.path.join(DATA_DIR, "annotations.json")

# Couleurs par annotateur (système de couleurs fixes)
ANNOTATOR_COLORS = {
    "default": "#FF0000",  # Rouge par défaut
    "remi": "#FF0000",     # Rouge
    "leslie": "#00FF00",   # Vert
    "yvab": "#0000FF",     # Bleu
    "demo": "#FF8000",     # Orange
    "test": "#8000FF",     # Violet
    "user1": "#00FFFF",    # Cyan
    "user2": "#FFFF00",    # Jaune
    "user3": "#FF00FF",    # Magenta
    "admin": "#000000",    # Noir
}

def ensure_dirs():
    """Crée les répertoires nécessaires."""
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

def get_annotator_color(annotator: str) -> str:
    """Retourne la couleur associée à un annotateur."""
    return ANNOTATOR_COLORS.get(annotator.lower(), ANNOTATOR_COLORS["default"])

def list_images():
    """Liste triée des fichiers image dans data/cars_detection/."""
    ensure_dirs()
    imgs = [f for f in os.listdir(IMAGES_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    imgs.sort()
    return imgs

def get_annotations_for_image(image_name: str) -> List[Dict]:
    """Récupère toutes les annotations pour une image donnée."""
    annotations = get_all_annotations()
    return [ann for ann in annotations if ann["image"] == image_name]

def update_annotation(annotation_id: str, new_rectangles: List[Dict], modifier_name: str = None, added_count: int = 0) -> bool:
    """Met à jour une annotation existante en remplaçant ses rectangles et enregistre l'historique."""
    try:
        data = load_annotations()
        
        # Trouver l'annotation à mettre à jour
        annotation_found = False
        for annotation in data.get("annotations", []):
            if annotation["id"] == annotation_id:
                old_count = len(annotation["rectangles"])
                
                # Remplacer les rectangles par les nouveaux (anciens + nouveaux)
                annotation["rectangles"] = new_rectangles
                annotation["last_updated"] = datetime.now().isoformat()
                
                # Ajouter l'entrée à l'historique si un modificateur est fourni
                if modifier_name and added_count > 0:
                    if "modification_history" not in annotation:
                        annotation["modification_history"] = []
                    
                    history_entry = {
                        "modifier_name": modifier_name,
                        "timestamp": datetime.now().isoformat(),
                        "rectangles_added": added_count,
                        "total_rectangles_after": len(new_rectangles),
                        "action": "ajout"
                    }
                    annotation["modification_history"].append(history_entry)
                
                annotation_found = True
                break
        
        if not annotation_found:
            print(f"Annotation avec ID {annotation_id} non trouvée")
            return False
        
        # Sauvegarder les modifications
        data["metadata"]["last_updated"] = datetime.now().isoformat()
        save_annotations(data)
        print(f"Annotation {annotation_id} mise à jour avec {len(new_rectangles)} rectangles")
        return True
        
    except Exception as e:
        print(f"Erreur lors de la mise à jour de l'annotation: {e}")
        return False

def load_annotations() -> Dict:
    """Charge le fichier d'annotations JSON."""
    ensure_dirs()
    if not os.path.exists(ANNOTATIONS_JSON):
        # Créer un fichier vide avec la structure initiale
        initial_data = {
            "metadata": {
                "version": "1.0",
                "created": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "next_id": 1
            },
            "annotations": []
        }
        with open(ANNOTATIONS_JSON, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, indent=2, ensure_ascii=False)
        return initial_data
    
    with open(ANNOTATIONS_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_annotations(data: Dict):
    """Sauvegarde le fichier d'annotations JSON."""
    data["metadata"]["last_updated"] = datetime.now().isoformat()
    with open(ANNOTATIONS_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_next_id() -> int:
    """Obtient le prochain ID disponible."""
    data = load_annotations()
    current_id = data["metadata"]["next_id"]
    data["metadata"]["next_id"] = current_id + 1
    save_annotations(data)
    return current_id

def add_annotation(image: str, annotator: str, rectangles: List[Dict]) -> int:
    """
    Ajoute une nouvelle annotation.
    
    Args:
        image: nom du fichier image (ex: car425.jpg)
        annotator: nom de l'annotateur
        rectangles: liste de rectangles [{"x": 100, "y": 50, "width": 200, "height": 100}]
    
    Returns:
        int: ID de l'annotation créée
    """
    data = load_annotations()
    annotation_id = data["metadata"]["next_id"]
    data["metadata"]["next_id"] = annotation_id + 1
    
    # Ajouter la couleur de l'annotateur à chaque rectangle
    rectangles_with_color = []
    annotator_color = get_annotator_color(annotator)
    
    for rect in rectangles:
        rect_with_color = rect.copy()
        rect_with_color["color"] = annotator_color
        rectangles_with_color.append(rect_with_color)
    
    new_annotation = {
        "id": annotation_id,
        "image": image,
        "annotator": annotator,
        "timestamp": datetime.now().isoformat(),
        "rectangles": rectangles_with_color
    }
    
    data["annotations"].append(new_annotation)
    save_annotations(data)
    return annotation_id

def get_annotations_for_image(image: str) -> List[Dict]:
    """Récupère toutes les annotations pour une image donnée, incluant les modifications."""
    data = load_annotations()
    return [ann for ann in data["annotations"] if ann["image"] == image]

def get_original_annotations_for_image(image: str) -> List[Dict]:
    """Récupère seulement les annotations originales (non modifications) pour une image."""
    data = load_annotations()
    return [ann for ann in data["annotations"] 
            if ann["image"] == image and not ann.get("is_modification", False)]

def get_final_annotations_for_image(image: str) -> List[Dict]:
    """
    Récupère les annotations finales pour une image : originales + dernières modifications.
    Pour chaque annotation originale, si elle a des modifications, prend la plus récente.
    """
    all_annotations = get_annotations_for_image(image)
    
    # Séparer originales et modifications
    originals = [ann for ann in all_annotations if not ann.get("is_modification", False)]
    modifications = [ann for ann in all_annotations if ann.get("is_modification", False)]
    
    final_annotations = []
    
    for original in originals:
        # Chercher les modifications de cette annotation
        original_mods = [mod for mod in modifications if mod.get("modifies_annotation_id") == original["id"]]
        
        if original_mods:
            # Prendre la modification la plus récente
            latest_mod = max(original_mods, key=lambda x: x["timestamp"])
            final_annotations.append(latest_mod)
        else:
            # Pas de modification, garder l'original
            final_annotations.append(original)
    
    return final_annotations

def get_annotations_by_annotator(annotator: str) -> List[Dict]:
    """Récupère toutes les annotations d'un annotateur donné."""
    data = load_annotations()
    return [ann for ann in data["annotations"] if ann["annotator"] == annotator]

def get_all_annotations() -> List[Dict]:
    """Récupère toutes les annotations."""
    data = load_annotations()
    return data["annotations"]

def get_annotation_by_id(annotation_id: int) -> Optional[Dict]:
    """Récupère une annotation par son ID."""
    data = load_annotations()
    for ann in data["annotations"]:
        if ann["id"] == annotation_id:
            return ann
    return None

def delete_annotation(annotation_id: int) -> bool:
    """Supprime une annotation par son ID."""
    data = load_annotations()
    for i, ann in enumerate(data["annotations"]):
        if ann["id"] == annotation_id:
            del data["annotations"][i]
            save_annotations(data)
            return True
    return False

def get_annotator_stats() -> Dict[str, Dict]:
    """Statistiques par annotateur."""
    data = load_annotations()
    stats = {}
    
    for ann in data["annotations"]:
        annotator = ann["annotator"]
        if annotator not in stats:
            stats[annotator] = {
                "color": get_annotator_color(annotator),
                "total_annotations": 0,
                "total_rectangles": 0,
                "images": set()
            }
        
        stats[annotator]["total_annotations"] += 1
        stats[annotator]["total_rectangles"] += len(ann["rectangles"])
        stats[annotator]["images"].add(ann["image"])
    
    # Convertir les sets en listes pour la sérialisation JSON
    for annotator in stats:
        stats[annotator]["images"] = len(stats[annotator]["images"])
    
    return stats

def create_sample_annotations():
    """Crée des annotations d'exemple."""
    images = list_images()
    if not images:
        print("Aucune image trouvée pour créer des exemples")
        return
    
    # Exemples d'annotations
    samples = [
        {
            "image": images[0] if len(images) > 0 else "car425.jpg",
            "annotator": "demo",
            "rectangles": [
                {"x": 100, "y": 50, "width": 200, "height": 100},
                {"x": 50, "y": 200, "width": 150, "height": 80}
            ]
        },
        {
            "image": images[1] if len(images) > 1 else "car426.jpg", 
            "annotator": "leslie",
            "rectangles": [
                {"x": 200, "y": 100, "width": 300, "height": 150}
            ]
        },
        {
            "image": images[0] if len(images) > 0 else "car425.jpg",
            "annotator": "remi", 
            "rectangles": [
                {"x": 300, "y": 150, "width": 100, "height": 120}
            ]
        }
    ]
    
    created_count = 0
    for sample in samples:
        annotation_id = add_annotation(
            sample["image"], 
            sample["annotator"], 
            sample["rectangles"]
        )
        print(f"Annotation #{annotation_id} créée pour {sample['image']} par {sample['annotator']}")
        created_count += 1
    
    return created_count

def modify_annotation(original_annotation_id: int, modifier_name: str, new_rectangles: List[Dict]) -> int:
    """
    Modifie une annotation existante en créant une entrée de modification.
    
    Args:
        original_annotation_id: ID de l'annotation originale à modifier
        modifier_name: Nom de la personne qui fait la modification
        new_rectangles: Nouveaux rectangles (remplacent complètement les anciens)
    
    Returns:
        ID de la nouvelle entrée de modification
    """
    data = load_annotations()
    
    # Trouver l'annotation originale
    original_annotation = None
    for ann in data["annotations"]:
        if ann["id"] == original_annotation_id:
            original_annotation = ann
            break
    
    if not original_annotation:
        raise ValueError(f"Annotation {original_annotation_id} non trouvée")
    
    # Ajouter la couleur aux rectangles
    modifier_color = get_annotator_color(modifier_name)
    rectangles_with_color = []
    for rect in new_rectangles:
        rect_with_color = rect.copy()
        rect_with_color["color"] = modifier_color
        rectangles_with_color.append(rect_with_color)
    
    # Créer la nouvelle entrée de modification
    new_id = data["metadata"]["next_id"]
    modification_entry = {
        "id": new_id,
        "image": original_annotation["image"],
        "annotator": modifier_name,
        "timestamp": datetime.now().isoformat(),
        "rectangles": rectangles_with_color,
        "is_modification": True,
        "modifies_annotation_id": original_annotation_id
    }
    
    # Ajouter au fichier
    data["annotations"].append(modification_entry)
    data["metadata"]["next_id"] += 1
    data["metadata"]["last_updated"] = datetime.now().isoformat()
    
    save_annotations(data)
    return new_id

def get_annotation_with_modifications(annotation_id: int) -> Dict:
    """
    Récupère une annotation avec toutes ses modifications.
    
    Returns:
        {
            "original": {...},
            "modifications": [{...}, {...}]
        }
    """
    annotations = get_all_annotations()
    
    # Trouver l'annotation originale
    original = None
    for ann in annotations:
        if ann["id"] == annotation_id and not ann.get("is_modification", False):
            original = ann
            break
    
    if not original:
        return None
    
    # Trouver toutes les modifications
    modifications = []
    for ann in annotations:
        if ann.get("modifies_annotation_id") == annotation_id:
            modifications.append(ann)
    
    # Trier les modifications par date
    modifications.sort(key=lambda x: x["timestamp"])
    
    return {
        "original": original,
        "modifications": modifications
    }
import os
import json
from datetime import datetime

class ConfigProfile:
    """Représente un profil de configuration enregistré"""
    def __init__(self, name, description="", config_data=None, creation_date=None):
        self.name = name
        self.description = description
        self.config_data = config_data or {}
        self.creation_date = creation_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "config_data": self.config_data,
            "creation_date": self.creation_date
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            config_data=data.get("config_data", {}),
            creation_date=data.get("creation_date", None)
        )

class ProfileManager:
    """Gestionnaire de profils de configuration"""
    def __init__(self, profile_dir=None):
        """
        Initialise le gestionnaire de profils
        
        Args:
            profile_dir (str): Dossier où seront stockés les profils.
                               Par défaut: "profiles" dans le répertoire de l'application
        """
        if profile_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            profile_dir = os.path.join(base_dir, "profiles")
        
        self.profile_dir = profile_dir
        
        # S'assurer que le dossier existe
        os.makedirs(self.profile_dir, exist_ok=True)
    
    def save_profile(self, profile):
        """Enregistre un profil"""
        if not isinstance(profile, ConfigProfile):
            raise ValueError("Le paramètre profile doit être une instance de ConfigProfile")
        
        # Nettoyer le nom pour créer un nom de fichier valide
        safe_name = "".join(c for c in profile.name if c.isalnum() or c in " _-").strip().replace(" ", "_")
        if not safe_name:
            safe_name = "profile_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        
        file_path = os.path.join(self.profile_dir, f"{safe_name}.json")
        
        # Vérifier si le fichier existe déjà
        counter = 1
        original_safe_name = safe_name
        while os.path.exists(file_path):
            safe_name = f"{original_safe_name}_{counter}"
            file_path = os.path.join(self.profile_dir, f"{safe_name}.json")
            counter += 1
        
        # Enregistrer le profil
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(profile.to_dict(), f, indent=2)
        
        return file_path
    
    def load_profile(self, profile_name):
        """Charge un profil par nom"""
        file_path = os.path.join(self.profile_dir, f"{profile_name}.json")
        
        if not os.path.exists(file_path):
            # Vérifier si le nom contient l'extension
            if not profile_name.endswith('.json'):
                file_path = os.path.join(self.profile_dir, f"{profile_name}")
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"Le profil {profile_name} n'existe pas")
            else:
                raise FileNotFoundError(f"Le profil {profile_name} n'existe pas")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return ConfigProfile.from_dict(data)
    
    def list_profiles(self):
        """Liste tous les profils disponibles"""
        profiles = []
        
        for filename in os.listdir(self.profile_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(self.profile_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    profile_name = data.get("name", filename[:-5])  # Enlever l'extension .json
                    profile_desc = data.get("description", "")
                    profile_date = data.get("creation_date", "")
                    
                    profiles.append({
                        "name": profile_name,
                        "filename": filename,
                        "description": profile_desc,
                        "date": profile_date
                    })
                except Exception as e:
                    print(f"Erreur lors du chargement du profil {filename}: {e}")
        
        return profiles
    
    def delete_profile(self, profile_name):
        """Supprime un profil par nom"""
        # Normaliser le nom en ajoutant l'extension si nécessaire
        if not profile_name.endswith('.json'):
            profile_name += '.json'
        
        file_path = os.path.join(self.profile_dir, profile_name)
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Le profil {profile_name} n'existe pas")
        
        os.remove(file_path)
        return True

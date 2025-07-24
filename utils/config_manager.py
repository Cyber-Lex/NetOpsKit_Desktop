import os
import json
import logging
import copy  # <--- ajout
from typing import Any, Dict, Optional

class ConfigManager:
    """Gestionnaire de configuration pour l'application NetOpsKit"""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialise le gestionnaire de configuration.
        
        Args:
            config_file: Chemin vers le fichier de configuration.
                         Si None, utilise le chemin par défaut.
        """
        self.logger = logging.getLogger(__name__)
        
        if config_file is None:
            # Chemin par défaut dans le dossier utilisateur
            config_dir = os.path.join(os.path.expanduser('~'), '.netopskit')
            os.makedirs(config_dir, exist_ok=True)
            config_file = os.path.join(config_dir, 'config.json')
        
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Charge et fusionne la configuration sans muter le modèle par défaut."""
        default_config = {
            "general": {
                "theme": "default",
                "language": "fr",
                "check_updates": True,
                "debug_mode": False
            },
            "network": {
                "timeout": 5,
                "max_threads": 20,
                "default_port": 22
            },
            "tftp": {
                "server_port": 69,
                "default_dir": os.path.join(os.path.expanduser('~'), 'tftp')
            },
            "syslog": {
                "listen_port": 514,
                "max_messages": 10000
            },
            "recent_files": [],
            "recent_connections": []
        }
        # Charge la config utilisateur si elle existe
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
            else:
                user_config = {}
        except Exception as e:
            self.logger.error(f"Impossible de lire {self.config_file}: {e}")
            user_config = {}

        # Fusionner dans une copie profonde du modèle
        merged = copy.deepcopy(default_config)
        for section, value in user_config.items():
            if section in merged and isinstance(merged[section], dict) and isinstance(value, dict):
                merged[section].update(value)
            else:
                merged[section] = value

        # Sauvegarde uniquement si quelque chose a changé ou si le fichier n'existait pas
        if merged != user_config:
            self._save_config(merged)
        return merged
    
    def _save_config(self, config: Dict[str, Any]) -> bool:
        """Sauvegarde la configuration dans le fichier"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde de la configuration: {e}")
            return False
    
    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        """
        Récupère une valeur de configuration.
        
        Args:
            section: La section de configuration
            key: La clé dans la section. Si None, retourne la section entière
            default: Valeur par défaut si la clé n'existe pas
        
        Returns:
            La valeur de configuration ou la valeur par défaut
        """
        if section not in self.config:
            return default
            
        if key is None:
            return self.config[section]
            
        return self.config[section].get(key, default)
    
    def set(self, section: str, key: str, value: Any) -> bool:
        """
        Définit une valeur de configuration.
        
        Args:
            section: La section de configuration
            key: La clé dans la section
            value: La valeur à définir
        
        Returns:
            True si la sauvegarde a réussi, False sinon
        """
        if section not in self.config:
            self.config[section] = {}
            
        self.config[section][key] = value
        return self._save_config(self.config)
    
    def add_recent_file(self, file_path: str, max_entries: int = 10) -> None:
        """Ajoute un fichier récent à la liste"""
        recent_files = self.get("recent_files", default=[])
        
        # Supprimer si déjà présent
        if file_path in recent_files:
            recent_files.remove(file_path)
            
        # Ajouter au début de la liste
        recent_files.insert(0, file_path)
        
        # Limiter la taille de la liste
        if len(recent_files) > max_entries:
            recent_files = recent_files[:max_entries]
            
        self.config["recent_files"] = recent_files
        self._save_config(self.config)
    
    def add_recent_connection(self, connection_info: Dict[str, Any], max_entries: int = 10) -> None:
        """Ajoute une connexion récente à la liste"""
        recent_connections = self.get("recent_connections", default=[])
        
        # Vérifier si déjà présent (par IP)
        for i, conn in enumerate(recent_connections):
            if conn.get("ip") == connection_info.get("ip"):
                recent_connections.pop(i)
                break
                
        # Ajouter au début de la liste
        recent_connections.insert(0, connection_info)
        
        # Limiter la taille de la liste
        if len(recent_connections) > max_entries:
            recent_connections = recent_connections[:max_entries]
            
        self.config["recent_connections"] = recent_connections
        self._save_config(self.config)

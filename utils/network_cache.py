import time
import threading
from collections import OrderedDict
from typing import Any, Optional, Tuple

class NetworkCache:
    """Cache optimisé pour les opérations réseau avec nettoyage périodique"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 60):
        """
        Initialise le cache réseau.
        
        Args:
            max_size (int): Taille maximale du cache
            ttl (int): Durée de vie des entrées en secondes
        """
        self._cache = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._lock = threading.RLock()
        
        # Démarrage du thread de nettoyage
        self._cleanup_thread = threading.Thread(target=self._cleanup_task, daemon=True)
        self._cleanup_thread.start()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Récupère une valeur du cache.
        
        Args:
            key (str): Clé de l'entrée
            
        Returns:
            La valeur associée à la clé ou None si non trouvée ou expirée
        """
        with self._lock:
            if key not in self._cache:
                return None
                
            value, timestamp = self._cache[key]
            
            # Vérifier si l'entrée a expiré
            if time.time() - timestamp > self._ttl:
                del self._cache[key]
                return None
                
            # Déplacer l'entrée à la fin (la plus récemment utilisée)
            self._cache.move_to_end(key)
            
            return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Ajoute ou met à jour une entrée dans le cache.
        
        Args:
            key (str): Clé de l'entrée
            value (Any): Valeur à stocker
        """
        with self._lock:
            # Si le cache est plein et que la clé n'existe pas déjà,
            # supprimer l'entrée la plus ancienne
            if len(self._cache) >= self._max_size and key not in self._cache:
                self._cache.popitem(last=False)
            
            # Ajouter ou mettre à jour l'entrée
            self._cache[key] = (value, time.time())
    
    def clear(self) -> None:
        """Vide le cache"""
        with self._lock:
            self._cache.clear()
    
    def size(self) -> int:
        """Retourne la taille actuelle du cache"""
        with self._lock:
            return len(self._cache)
    
    def _cleanup_task(self) -> None:
        """Tâche de nettoyage qui supprime les entrées expirées"""
        while True:
            time.sleep(self._ttl / 2)  # Nettoyage périodique
            self._cleanup_expired()
    
    def _cleanup_expired(self) -> None:
        """Supprime les entrées expirées du cache"""
        now = time.time()
        with self._lock:
            # Identifie les clés à supprimer
            expired_keys = [
                key for key, (_, timestamp) in self._cache.items()
                if now - timestamp > self._ttl
            ]
            
            # Supprime les clés expirées
            for key in expired_keys:
                del self._cache[key]

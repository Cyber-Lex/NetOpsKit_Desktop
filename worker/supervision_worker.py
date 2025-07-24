from PyQt5.QtCore import QObject, QRunnable, pyqtSignal
from datetime import datetime
import subprocess
import platform
import time
import logging
import socket
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
import psutil

logger = logging.getLogger("SupervisionApp")

def ping(ip, timeout=2):
    """Fonction de ping optimisée avec cache de résultats"""
    try:
        start_time = time.perf_counter()
        
        # Préparer la commande de ping en fonction du système d'exploitation
        if platform.system().lower() == "windows":
            # Utiliser -n pour le nombre de pings, -w pour le timeout (en ms)
            cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
        else:
            # Utiliser -c pour le nombre de pings, -W pour le timeout (en sec)
            cmd = ["ping", "-c", "1", "-W", str(timeout), ip]
        
        # Exécuter la commande avec redirect stderr vers stdout pour capturer toutes les erreurs
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout + 1,
            check=False,  # Ne pas lever d'exception si le code de retour n'est pas 0
            text=True      # Obtenir directement une chaîne de caractères
        )
        
        latency = (time.perf_counter() - start_time) * 1000
        success = result.returncode == 0
        
        # Log détaillé en cas d'échec
        if not success and logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Ping échec pour {ip}: {result.stdout}")
            
        return success, latency
    except subprocess.TimeoutExpired:
        logger.debug(f"Timeout du ping pour l'IP {ip}")
        return False, 0
    except Exception as e:
        logger.debug(f"Erreur lors du ping de l'IP {ip}: {e}")
        return False, 0

class PingWorkerSignals(QObject):
    finished = pyqtSignal(object, bool, float)

class PingWorker(QRunnable):
    def __init__(self, equipment_item, supervision_widget, timeout=1):
        super().__init__()
        self.equipment_item = equipment_item
        self.supervision_widget = supervision_widget
        self.timeout = timeout
        self.signals = PingWorkerSignals()

    def run(self):
        cached = self.supervision_widget.ping_cache.get(self.equipment_item.ip)
        if cached is not None:
            self.signals.finished.emit(self.equipment_item, cached[0], cached[1])
            return
        status, latency = ping(self.equipment_item.ip, self.timeout)
        self.supervision_widget.ping_cache.set(self.equipment_item.ip, (status, latency))
        self.signals.finished.emit(self.equipment_item, status, latency)

class NetworkDiscoveryWorkerSignals(QObject):
    discovered = pyqtSignal(str)
    progress = pyqtSignal(int, int)
    finished = pyqtSignal()

class NetworkDiscoveryWorker(QRunnable):
    def __init__(self, subnet):
        super().__init__()
        self.original_subnet = subnet
        self.signals = NetworkDiscoveryWorkerSignals()
        self.is_running = True
        
        # Valider et parser le subnet
        if "/" in subnet:
            try:
                network = ipaddress.ip_network(subnet, strict=False)
                # Limiter le nombre d'hôtes à scanner pour des raisons de performance
                if network.num_addresses > 1024:
                    logger.warning(f"Réseau {subnet} très grand ({network.num_addresses}). "
                                  f"Limitation à 1024 adresses pour éviter une surcharge.")
                    self.hosts = [str(ip) for ip in list(network.hosts())[:1024]]
                else:
                    self.hosts = [str(ip) for ip in network.hosts()]
            except Exception as e:
                logger.error(f"Erreur parsing CIDR: {e}")
                self.hosts = []
        else:
            if not subnet.endswith("."):
                subnet += "."
            self.hosts = [subnet + str(i) for i in range(1, 255)]

    def run(self):
        total = len(self.hosts)
        if total == 0:
            self.signals.finished.emit()
            return
            
        # Limiter le nombre de workers en fonction des ressources disponibles
        cpu_count = psutil.cpu_count() or 2
        max_workers = min(20, cpu_count * 2)  # Ajuster en fonction du nombre de CPUs
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(ping, ip, 0.5): ip for ip in self.hosts if self.is_running}
            completed = 0
            
            # Mettre à jour la progression par lots pour réduire les mises à jour d'UI
            update_interval = max(1, total // 20)  # 5% d'intervalle de mise à jour
            
            for future in as_completed(futures):
                if not self.is_running:
                    break
                    
                ip = futures[future]
                try:
                    status, _ = future.result()
                    if status:
                        self.signals.discovered.emit(ip)
                except Exception as e:
                    logger.warning(f"Erreur lors du scan de {ip}: {e}")
                
                completed += 1
                if completed % update_interval == 0 or completed == total:
                    self.signals.progress.emit(completed, total)
            
        self.signals.finished.emit()

    def stop(self):
        self.is_running = False

class ScanNetworkWorkerSignals(QObject):
    progress = pyqtSignal(int, int)
    device_found = pyqtSignal(str, str)
    finished = pyqtSignal()

class ScanNetworkWorker(QRunnable):
    def __init__(self, network_range, scan_ports=False, fast_mode=True):
        super().__init__()
        self.network_range = network_range
        self.scan_ports = scan_ports
        self.fast_mode = fast_mode
        self.signals = ScanNetworkWorkerSignals()
        self.is_running = True
        self._ip_cache = {}  # Cache de résultats

    def run(self):
        try:
            network = ipaddress.IPv4Network(self.network_range, strict=False)
            total_ips = list(network.hosts())
            
            # Limiter le nombre d'IPs scannées si le réseau est trop grand
            if len(total_ips) > 1024:
                logger.warning(f"Le réseau {self.network_range} est trop grand. Limitation à 1024 adresses.")
                total_ips = total_ips[:1024]
            
            # Adapter le nombre de workers et le timeout en fonction du mode
            max_workers = 50 if not self.fast_mode else 100
            timeout = 1 if not self.fast_mode else 0.5
            
            # Utiliser ThreadPoolExecutor pour les scans parallèles
            futures_dict = {}
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Soumettre les tâches en batch pour éviter surcharge
                batch_size = 50
                for batch_start in range(0, len(total_ips), batch_size):
                    if not self.is_running:
                        break
                        
                    # Prendre un lot d'IPs
                    batch_end = min(batch_start + batch_size, len(total_ips))
                    batch_ips = total_ips[batch_start:batch_end]
                    
                    # Soumettre les tâches pour ce lot
                    for ip in batch_ips:
                        ip_str = str(ip)
                        # Vérifier si l'IP est dans le cache
                        if ip_str in self._ip_cache:
                            info = self._ip_cache[ip_str]
                            if info:
                                self.signals.device_found.emit(ip_str, info)
                        else:
                            future = executor.submit(self.scan_ip, ip_str, timeout)
                            futures_dict[future] = ip_str
                    
                    # Mise à jour de progression après chaque lot
                    self.signals.progress.emit(batch_end, len(total_ips))
                
                # Traiter les résultats
                for future in as_completed(futures_dict):
                    if not self.is_running:
                        break
                    
                    ip = futures_dict[future]
                    try:
                        info = future.result()
                        # Mettre en cache le résultat
                        self._ip_cache[ip] = info
                        
                        if info:
                            self.signals.device_found.emit(ip, info)
                    except Exception as e:
                        logger.warning(f"Erreur scan {ip}: {e}")
                
            self.signals.finished.emit()
        except Exception as e:
            logger.error(f"Erreur scan réseau: {e}")
            self.signals.finished.emit()
    
    def scan_ip(self, ip, timeout=0.5):
        if not self.is_running:
            return None
        status, latency = ping(ip, timeout)
        if not status:
            return None
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except Exception:
            hostname = "Inconnu"
        open_ports = ""
        if self.scan_ports:
            open_ports = "Ports: 22,80"
        return f"{hostname}|{open_ports}"

    def stop(self):
        self.is_running = False

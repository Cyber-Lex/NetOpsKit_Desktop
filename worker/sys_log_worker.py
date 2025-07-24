import socket
import threading
from datetime import datetime
import queue
import time
import select
import logging
from PyQt5.QtCore import QObject, pyqtSignal
from typing import Optional, Dict, Any
import signal

from views.sys_log import SyslogParser, ServerConfig, SyslogStats

class SyslogServerSignals(QObject):
    new_message = pyqtSignal(str, str, int, int, str)  # (timestamp, source, facility, severity, message)
    log_message = pyqtSignal(str, str)  # (niveau, message)
    server_started = pyqtSignal(str, int)  # (host, port)
    server_stopped = pyqtSignal()
    stats_updated = pyqtSignal(dict)  # statistiques

class SyslogServerWorker(threading.Thread):
    def __init__(self, config: ServerConfig, signals: SyslogServerSignals, stats: SyslogStats):
        super().__init__()
        self.config = config
        self.signals = signals
        self.stats = stats
        self.running = False
        self.sock: Optional[socket.socket] = None
        self.daemon = True
        self.message_queue = queue.Queue(maxsize=10000)
        self.processor_thread = None
        self.stats_update_interval = 5  # Intervalle de mise à jour des statistiques en secondes
        self.last_stats_update = time.time()
    
    def run(self) -> None:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.config.host, self.config.port))
            self.sock.settimeout(0.5)  # Ajouter un timeout pour permettre la vérification de running
            
            self.running = True
            self.signals.server_started.emit(self.config.host, self.config.port)
            
            # Démarrage du thread de traitement
            self.processor_thread = threading.Thread(target=self._process_messages)
            self.processor_thread.daemon = True
            self.processor_thread.start()
            
            self._receive_loop()
        except Exception as e:
            self.signals.log_message.emit("ERROR", f"Erreur lors du démarrage du thread: {e}")
        finally:
            self._cleanup()

    def stop(self) -> None:
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception as e:
                logging.error(f"Erreur lors de la fermeture du socket: {e}")
        
        # Attendre que le thread de traitement se termine
        if self.processor_thread and self.processor_thread.is_alive():
            self.processor_thread.join(timeout=2)
            if self.processor_thread.is_alive():
                logging.warning("Le thread de traitement ne s'est pas terminé correctement")
        
        self.signals.server_stopped.emit()

    def _cleanup(self) -> None:
        """Nettoie les ressources lors de l'arrêt"""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        # Vider la file d'attente pour libérer la mémoire
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
            except queue.Empty:
                break

    def _receive_loop(self) -> None:
        """Boucle de réception optimisée avec mise en buffer"""
        message_buffer = []
        buffer_size = 100  # Taille du buffer
        buffer_timeout = 0.1  # Timeout en secondes
        last_flush = time.time()

        while self.running:
            try:
                ready = select.select([self.sock], [], [], buffer_timeout)
                current_time = time.time()
                
                if ready[0]:
                    data, addr = self.sock.recvfrom(self.config.buffer_size)
                    message_buffer.append((data, addr, current_time))
                
                # Vider le buffer si plein ou timeout atteint
                if len(message_buffer) >= buffer_size or (current_time - last_flush) >= buffer_timeout:
                    self._process_buffer(message_buffer)
                    message_buffer = []
                    last_flush = current_time
                    
            except Exception as e:
                if self.running:
                    self.signals.log_message.emit("ERROR", f"Erreur de réception: {e}")
                    time.sleep(0.1)  # Éviter la surcharge en cas d'erreur

    def _process_buffer(self, message_buffer):
        """Traitement optimisé du buffer de messages"""
        for data, addr, timestamp in message_buffer:
            try:
                message = data.decode('utf-8', errors='replace').strip()
                self.message_queue.put((message, addr, timestamp))
            except Exception as e:
                self.signals.log_message.emit("ERROR", f"Erreur décodage: {e}")

    def _process_messages(self):
        batch_size = 50  # Nombre de messages à traiter par lot
        messages_processed = 0
        
        while self.running:
            try:
                # Traiter un lot de messages
                batch = []
                for _ in range(batch_size):
                    try:
                        message, addr, timestamp = self.message_queue.get(block=False)
                        batch.append((message, addr, timestamp))
                        messages_processed += 1
                    except queue.Empty:
                        break
                
                # Traiter le lot
                for message, addr, timestamp in batch:
                    src_ip = addr[0]
                    src_port = addr[1]
                    src = f"{src_ip}:{src_port}"

                    try:
                        facility_num, severity_num, parsed_message = SyslogParser.parse_syslog_message(message)
                        self.stats.update(src_ip, facility_num, severity_num)

                        if self._should_process_message(src_ip, facility_num, severity_num, parsed_message):
                            self.signals.new_message.emit(timestamp, src, facility_num, severity_num, parsed_message)

                    except Exception as e:
                        self.signals.log_message.emit("ERROR", f"Erreur lors du traitement du message: {e}")
                
                # Mise à jour des statistiques périodiquement
                current_time = time.time()
                if current_time - self.last_stats_update >= self.stats_update_interval:
                    self.signals.stats_updated.emit(self.stats.get_stats())
                    self.last_stats_update = current_time
                
                # Pause si aucun message n'a été traité
                if not batch:
                    time.sleep(0.1)
                    
            except Exception as e:
                if self.running:
                    self.signals.log_message.emit("ERROR", f"Erreur dans le traitement des messages: {e}")
                time.sleep(0.2)  # Éviter de surcharger en cas d'erreur

    def _should_process_message(self, src_ip: str, facility_num: int, severity_num: int, message: str) -> bool:
        """Vérifie si le message doit être traité selon les filtres configurés"""
        if self.config.filters["enabled"]:
            if self.config.filters["hosts"] and src_ip not in self.config.filters["hosts"]:
                return False
            if self.config.filters["facilities"] and facility_num not in self.config.filters["facilities"]:
                return False
            if self.config.filters["severities"] and severity_num not in self.config.filters["severities"]:
                return False
            if self.config.filters["keywords"]:
                if not any(keyword.lower() in message.lower() for keyword in self.config.filters["keywords"]):
                    return False
        return True

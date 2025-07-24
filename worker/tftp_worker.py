from PyQt5.QtCore import QObject, pyqtSignal
import threading
import time
import logging
from datetime import datetime
import queue

class TFTPServerSignals(QObject):
    log_message = pyqtSignal(str, str)   # niveau, message
    client_connected = pyqtSignal(str, dict)   # client_id, infos
    client_disconnected = pyqtSignal(str)
    transfer_started = pyqtSignal(str, dict)     # client_id, infos transfert
    transfer_updated = pyqtSignal(str, dict)     # client_id, infos transfert
    transfer_completed = pyqtSignal(str, bool)   # client_id, succès

class TFTPWorker(QObject):
    def __init__(self, server, parent=None):
        super().__init__(parent)
        self.server = server
        self.thread = None
        self.is_running = False
        self.signals = TFTPServerSignals()
        self.status_queue = queue.Queue(maxsize=100)  # Buffer pour les mises à jour de statut

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            logging.info("TFTP worker started")

    def stop(self):
        logging.info("Stopping TFTP worker...")
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
            if self.thread.is_alive():
                logging.warning("TFTP worker thread did not terminate properly")

    def _run(self):
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while self.is_running:
            try:
                status = self.server.get_status()
                consecutive_errors = 0  # Réinitialiser le compteur d'erreurs
                
                # Vérification des clients inactifs
                now = datetime.now()
                inactive_timeout = 300  # 5 minutes

                for client_id, client in status['clients'].items():
                    last_seen = client.get('last_seen')
                    if last_seen:
                        delta = (now - last_seen).total_seconds()
                        if delta > inactive_timeout and client.get('active', False):
                            self.signals.client_disconnected.emit(client_id)
                            client['active'] = False

                # Mise à jour des transferts actifs
                for client_id, transfer in status['transfers'].items():
                    if not transfer.get('completed', False):
                        self.signals.transfer_updated.emit(client_id, transfer)

                # Ajuster le temps de pause en fonction de la charge
                sleep_time = 0.2
                time.sleep(sleep_time)
                
            except Exception as e:
                consecutive_errors += 1
                logging.error(f"Error in TFTP worker: {str(e)}")
                
                # Augmenter le temps de pause exponentiellement en cas d'erreurs consécutives
                if consecutive_errors > max_consecutive_errors:
                    logging.critical(f"Too many consecutive errors in TFTP worker, pausing for longer")
                    time.sleep(5)  # Pause plus longue après plusieurs erreurs
                else:
                    time.sleep(1)  # Pause standard en cas d'erreur

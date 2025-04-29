import socket
import time
import threading


class TCPClient:
    """
    TCP-Client Klasse für die Kommunikation mit dem Blender-Server.
    Diese Klasse stellt die Verbindung her, sendet und empfängt Nachrichten.
    """

    def __init__(self, host="localhost", port=65432):
        self.host = host
        self.port = port
        self.sock = None
        self.running = False
        self.lock = threading.Lock()  # Thread-Synchronisierung

    def start(self):
        """Startet den TCP-Client und stellt die Verbindung her."""
        if self.running:
            print("TCP-Client läuft bereits.")
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.running = True
            print(f"Connected to server at {self.host}:{self.port}")
        except Exception as e:
            print(f"Fehler beim Verbinden mit dem Server: {e}")
            self.running = False
            self.sock = None

    def reconnect(self):
        """Stellt die Verbindung zum Server wieder her, wenn sie unterbrochen wurde."""
        self.stop()  # Bestehende Verbindung schließen
        time.sleep(1)  # Kurze Pause

        # Neue Verbindung herstellen
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.host, self.port))
                self.running = True
                print(f"Reconnected to server at {self.host}:{self.port}")
                return True
            except Exception as e:
                print(f"Reconnect-Versuch {attempt + 1}/{max_retries} fehlgeschlagen: {e}")
                time.sleep(2)  # Pause zwischen Versuchen

        print("Alle Reconnect-Versuche fehlgeschlagen.")
        self.running = False
        return False

    def stop(self):
        """Stoppt den TCP-Client und schließt die Verbindung."""
        with self.lock:
            if self.sock:
                try:
                    self.sock.close()
                except:
                    pass
                self.sock = None
            self.running = False
            print("TCP client stopped.")

    def send_message(self, message):
        """Sendet eine Nachricht an den Server."""
        if not self.running or not self.sock:
            raise ConnectionError("Not connected to server")

        with self.lock:
            try:
                # Nachricht als UTF-8 kodieren und senden
                data = message.encode('utf-8')
                self.sock.sendall(data)
                print(f"Sent to server: {message}")
                return True
            except Exception as e:
                print(f"Fehler beim Senden der Nachricht: {e}")
                self.running = False
                raise

    def receive_message(self, timeout=30.0):
        """
        Empfängt eine Nachricht vom Server.

        Args:
            timeout: Timeout in Sekunden für den Empfang

        Returns:
            Empfangene Nachricht als String oder None bei Timeout/Fehler
        """
        if not self.running or not self.sock:
            print("Nicht mit dem Server verbunden.")
            return None

        with self.lock:
            try:
                # Timeout setzen
                self.sock.settimeout(timeout)

                # Buffer für das Empfangen der Daten
                buffer_size = 4096
                data = b""

                # Daten empfangen
                chunk = self.sock.recv(buffer_size)
                if not chunk:
                    print("Verbindung zum Server geschlossen.")
                    self.running = False
                    return None

                data += chunk

                # Zurücksetzen des Timeouts
                self.sock.settimeout(None)

                # Daten dekodieren und zurückgeben
                message = data.decode('utf-8')
                return message

            except socket.timeout:
                print(f"Timeout beim Empfangen der Nachricht nach {timeout} Sekunden.")
                return None
            except Exception as e:
                print(f"Failed to receive message: {e}")
                self.running = False
                return None
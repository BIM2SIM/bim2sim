import json
import time
from bim2sim.tcp_connection import TCPClient  # Beispielklasse für TCP-Interaktion
from bim2sim.kernel.decision.decisionhandler import DecisionHandler
from bim2sim.kernel.decision import DecisionBunch, DecisionSkip, DecisionCancel


class TCPDecisionHandler(DecisionHandler):
    """DecisionHandler mit TCP-Kommunikation."""

    def __init__(self, tcp_client: TCPClient):
        super().__init__()
        self.tcp_client = tcp_client
        self.ensure_client_running()

    def ensure_client_running(self):
        """Stellt sicher, dass der TCP-Client läuft."""
        if not self.tcp_client.running:
            self.tcp_client.start()

    # Antwortverarbeitung: Sicherstellen, dass das Antwortformat korrekt ist
    def get_answers_for_bunch(self, bunch: DecisionBunch) -> list:
        # Sofort leere Liste zurückgeben, wenn das Bunch leer ist
        if not bunch:
            print("Leeres DecisionBunch erhalten, gebe leere Liste zurück")
            return []

        message = {}
        identifier_map = {}
        decision_to_identifier = {}  # Mapping von Entscheidung zu Identifier

        # Entscheidungen vorbereiten und Nachricht aufbauen
        for i, decision in enumerate(bunch):
            identifier = decision.related or f"auto_id_{i}"
            identifier_map[identifier] = decision
            decision_to_identifier[decision] = identifier  # Reverse-Mapping speichern

            message[identifier] = {
                "question": self.get_question(decision),
                "identifier": decision.related,
                "options": self.get_options(decision),
                "default": decision.default if decision.default is not None else "",
                "type": type(decision).__name__,
                "body": self.get_body(decision) if hasattr(decision, "get_body") else []
            }

        # Nachricht an Client senden
        try:
            self.tcp_client.send_message(json.dumps(message))
        except Exception as e:
            print(f"Fehler beim Senden der Nachricht: {e}")
            # Verbindung wiederherstellen und erneut versuchen
            self.tcp_client.reconnect()
            self.tcp_client.send_message(json.dumps(message))

        # Auf Antwort warten mit Timeout und Wiederholungsversuchen
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                response = self.tcp_client.receive_message(timeout=10.0)  # 10 Sekunden Timeout
                if response is None:
                    print("Keine Antwort erhalten (Timeout)")
                    retry_count += 1
                    time.sleep(1)  # Kurze Pause vor dem nächsten Versuch
                    continue

                print(f"Received from server: {response}")

                # Leere Antwort oder leeres JSON verarbeiten
                if not response.strip() or response.strip() == "[]" or response.strip() == "{}":
                    print("Leere Antwort erhalten, verwende Standardwerte")
                    return [decision.default if decision.default is not None else 0 for decision in bunch]

                # Versuche Antwort zu parsen
                try:
                    extracted_responses = json.loads(response)
                except json.JSONDecodeError as e:
                    print(f"Fehler beim Parsen der Antwort: {e}")
                    retry_count += 1
                    continue

                parsed_responses = self.extract_answers(extracted_responses, identifier_map)

                if parsed_responses is None:
                    # Sende Fehlermeldung und versuche es erneut
                    retry_count += 1
                    time.sleep(1)
                    continue

                # Antworten in der richtigen Reihenfolge zusammenstellen
                answers = []
                for decision in bunch:
                    # Identifier aus dem gespeicherten Mapping holen
                    identifier = decision_to_identifier.get(decision)
                    if identifier in parsed_responses:
                        answers.append(parsed_responses[identifier])
                    else:
                        # Fallback: Standardwert verwenden
                        print(
                            f"Warnung: Keine Antwort für Entscheidung mit Identifier {identifier} gefunden. Verwende Default.")
                        default_value = decision.default
                        if default_value is None:
                            # Wenn kein Default definiert ist, verwenden wir 0 für ListDecision
                            if type(decision).__name__ == "ListDecision":
                                default_value = 0
                            else:
                                default_value = ""
                        answers.append(default_value)

                print(f"Parsed answers: {answers}")
                return answers

            except Exception as e:
                print(f"Fehler bei der Verarbeitung: {e}")
                retry_count += 1
                time.sleep(1)

        # Wenn alle Versuche fehlschlagen, verwenden wir Standardwerte
        print("Maximale Anzahl an Versuchen erreicht. Verwende Standardwerte.")
        return [decision.default if decision.default is not None else 0 for decision in bunch]

    def send_decision_to_client(self, decision):
        """Sendet eine Entscheidung an den TCP-Client und erhält die Antwort."""
        message = {
            "question": self.get_question(decision),
            "identifier": decision.related,
            "options": self.get_options(decision),
            "default": decision.default,
            "type": type(decision).__name__,
            # "related": decision.related
        }
        if hasattr(decision, "get_body"):
            message["body"] = decision.get_body()

        try:
            self.tcp_client.send_message(json.dumps(message))
        except Exception as e:
            print(f"Fehler beim Senden der Entscheidung: {e}")
            self.tcp_client.reconnect()
            self.tcp_client.send_message(json.dumps(message))

        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                response = self.tcp_client.receive_message(timeout=10.0)
                if response is None:
                    print("Keine Antwort erhalten (Timeout)")
                    retry_count += 1
                    time.sleep(1)
                    continue

                # Leere Antwort verarbeiten
                if not response.strip() or response.strip() == "[]" or response.strip() == "{}":
                    print("Leere Antwort erhalten, verwende Standardwert")
                    return decision.default

                extracted_response = self.extract_answer(response)
                parsed_response = self.parse(decision, extracted_response)

                if self.validate(decision, parsed_response):
                    return parsed_response
                else:
                    retry_count += 1
            except DecisionSkip:
                raise DecisionSkip
            except DecisionCancel:
                raise DecisionCancel
            except Exception as e:
                print(f"Fehler bei der Verarbeitung der Antwort: {e}")
                retry_count += 1
                time.sleep(1)

        # Standardwert zurückgeben, wenn keine gültige Antwort erhalten wurde
        print("Verwende Standardwert nach fehlgeschlagenen Versuchen.")
        return decision.default

    def shutdown(self, success):
        """Schließt die TCP-Verbindung, wenn erforderlich."""
        try:
            self.tcp_client.send_message("SHUTDOWN")
        except:
            pass
        self.tcp_client.stop()

    def extract_answers(self, response, identifier_map: dict):
        """
        Extrahiert die Antworten aus verschiedenen Antwortformaten und mapped sie
        auf die passenden Typen laut identifier_map.

        Unterstützt sowohl:
        - Einfaches dict mit identifier -> wert
        - Dict mit identifier -> {answer: wert, type: typ}
        - Liste von Objekten mit decision_id, answer, decision_type
        - Leere Liste oder Dict (gibt leeres Dictionary zurück)
        """
        answers = {}

        try:
            # Fall 0: Leere Antwort
            if response == [] or response == {}:
                print("Leere Antwort erhalten, gebe leeres Dictionary zurück")
                return {}

            # Fall 1: Antwort ist eine Liste von Objekten mit decision_id
            if isinstance(response, list):
                for item in response:
                    if isinstance(item, dict) and "decision_id" in item and "answer" in item:
                        identifier = item["decision_id"]
                        if identifier in identifier_map:
                            decision = identifier_map[identifier]
                            decision_type = type(decision).__name__
                            raw_answer = item["answer"]

                            # Für ListDecision akzeptieren wir sowohl Indizes als auch Namen
                            if decision_type == "ListDecision":
                                if isinstance(raw_answer, int) or (
                                        isinstance(raw_answer, str) and raw_answer.isdigit()):
                                    # Es ist ein Index - aber wir akzeptieren diesen direkt
                                    answers[identifier] = raw_answer
                                else:
                                    # Es ist ein String - wir nehmen ihn direkt
                                    answers[identifier] = raw_answer
                            else:
                                # Für andere Entscheidungstypen verwenden wir die normale Parsing-Methode
                                answers[identifier] = self._parse_value(raw_answer, decision_type)

            # Fall 2: Antwort ist ein Dictionary
            elif isinstance(response, dict):
                for identifier, raw_value in response.items():
                    if identifier in identifier_map:
                        decision = identifier_map[identifier]
                        decision_type = type(decision).__name__

                        # Fall 2a: Wert ist ein Objekt mit "answer" Feld
                        if isinstance(raw_value, dict) and "answer" in raw_value:
                            value = raw_value["answer"]
                        # Fall 2b: Wert ist direkt der Antwortwert
                        else:
                            value = raw_value

                        # Für alle Entscheidungstypen: Direkt den Wert verwenden
                        answers[identifier] = value
                    else:
                        print(f"Warnung: Unbekannter Identifier in Antwort: {identifier}")

            # Ungültiges Format
            else:
                print(f"Fehler: Antwortformat nicht unterstützt: {type(response)}")
                return None

            # Bei einer leeren Liste/Dict akzeptieren wir das als gültige Antwort
            if len(answers) == 0 and (isinstance(response, list) or isinstance(response, dict)):
                print("Leere Antwortliste/Dict erhalten, akzeptiert.")
                return {}

            return answers

        except Exception as e:
            print(f"Fehler beim Extrahieren der Antworten: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_value(self, value, decision_type):
        """Parst einen Wert basierend auf dem Entscheidungstyp."""
        try:
            if decision_type == "ListDecision":
                # Für ListDecision akzeptieren wir die Werte direkt
                return value

            elif decision_type == "RealDecision":
                return float(value)

            elif decision_type == "BoolDecision":
                if isinstance(value, bool):
                    return value
                elif isinstance(value, str):
                    return value.strip().lower() in ["true", "1", "yes", "ja"]
                elif isinstance(value, (int, float)):
                    return bool(value)
                else:
                    raise ValueError(f"BoolDecision erwartet einen bool-kompatiblen Wert, erhalten: {value}")

            elif decision_type == "StringDecision":
                return str(value)

            else:
                print(f"Warnung: Unbekannter Entscheidungstyp: {decision_type}, verwende Rohwert")
                return value

        except Exception as e:
            print(f"Fehler beim Parsen des Werts {value} für Typ {decision_type}: {str(e)}")
            raise
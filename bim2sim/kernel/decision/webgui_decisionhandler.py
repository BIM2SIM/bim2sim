"""
WebGUI DecisionHandler for bim2sim.

Handles decisions via the Web-GUI using shared state
between the handler and Flask server (same process).
"""

import json
import logging
import threading
import time
from typing import List, Dict, Any, Optional

from bim2sim.kernel.decision.decisionhandler import DecisionHandler
from bim2sim.kernel.decision import (
    DecisionBunch, ListDecision, RealDecision, BoolDecision
)

logger = logging.getLogger(__name__)


class WebGUIDecisionHandler(DecisionHandler):
    """DecisionHandler that communicates with a Web-GUI via shared state."""

    # Shared state - accessible by Flask server
    _instance: Optional['WebGUIDecisionHandler'] = None

    def __init__(self, socketio=None):
        super().__init__()

        # Pending decisions waiting for answers
        self.pending_bunch: Optional[DecisionBunch] = None
        self.pending_decisions_data: List[Dict[str, Any]] = []

        # Answers received from frontend
        self.received_answers: Dict[str, Any] = {}

        # Threading event to wait for answers
        self.answer_event = threading.Event()

        # Status
        self.is_waiting = False

        # SocketIO for broadcasting
        self.socketio = socketio

        # Set singleton instance
        WebGUIDecisionHandler._instance = self

        logger.info("WebGUIDecisionHandler initialized")

    @classmethod
    def get_instance(cls) -> Optional['WebGUIDecisionHandler']:
        """Get the current handler instance (for Flask server access)."""
        return cls._instance

    def get_answers_for_bunch(self, bunch: DecisionBunch) -> list:
        """
        Wait for answers from the Web-GUI.

        This method blocks until all decisions are answered via the frontend.
        """
        if not bunch:
            return []

        # Prepare decisions for frontend
        self.pending_bunch = bunch
        self.pending_decisions_data = self._serialize_bunch(bunch)
        self.received_answers = {}
        self.answer_event.clear()
        self.is_waiting = True

        logger.info(f"Waiting for {len(bunch)} decisions from Web-GUI...")

        # Broadcast that decisions are available
        if self.socketio:
            self.socketio.emit('decisions_available', {
                'count': len(bunch),
                'timestamp': time.time()
            })
            logger.info("Broadcasted 'decisions_available' event")

        # Block until answers received
        self.answer_event.wait()

        self.is_waiting = False
        logger.info("Answers received from Web-GUI")

        # Parse and return answers
        return self._parse_answers(bunch)

    def _serialize_bunch(self, bunch: DecisionBunch) -> List[Dict[str, Any]]:
        """Convert DecisionBunch to JSON-serializable format for frontend."""
        decisions_data = []

        for i, decision in enumerate(bunch):
            try:
                decision_data = {
                    'index': i,
                    'id': decision.global_key or f"decision_{i}",
                    'question': self.get_question(decision),
                    'type': type(decision).__name__,
                    'default': self._safe_json(decision.default),
                    'allow_skip': decision.allow_skip,
                    'related': self._safe_json(decision.related),
                    'context': self._safe_json(decision.context),
                }

                # Add type-specific data
                try:
                    body = self.get_body(decision)
                    if body:
                        decision_data['body'] = self._safe_json(body)
                except Exception as e:
                    logger.warning(f"Error getting body for decision {i}: {e}")

                try:
                    options = self.get_options(decision)
                    if options:
                        decision_data['options'] = self._safe_json(options)
                except Exception as e:
                    logger.warning(f"Error getting options for decision {i}: {e}")

                decisions_data.append(decision_data)

            except Exception as e:
                logger.error(f"Error serializing decision {i}: {e}")
                # Add minimal fallback entry so indexing stays consistent
                decisions_data.append({
                    'index': i,
                    'id': decision.global_key or f"decision_{i}",
                    'question': f"[Serialization error: {e}]",
                    'type': type(decision).__name__,
                    'default': None,
                    'allow_skip': True,
                    'related': None,
                    'context': None,
                })

        return decisions_data

    @staticmethod
    def _safe_json(obj):
        """Make an object safely JSON-serializable.

        Handles sets, tuples, custom objects, and other types that
        json.dumps would reject.
        """
        if obj is None:
            return None
        # Fast path: primitives are always safe
        if isinstance(obj, (str, int, float, bool)):
            return obj
        # Try direct serialization first (covers lists/dicts of primitives)
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError, OverflowError):
            pass
        # Convert common non-serializable types
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, tuple):
            return list(obj)
        if isinstance(obj, dict):
            return {str(k): WebGUIDecisionHandler._safe_json(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [WebGUIDecisionHandler._safe_json(item) for item in obj]
        # Last resort: string representation
        try:
            return str(obj)
        except Exception:
            return f"<non-serializable: {type(obj).__name__}>"

    def _parse_answers(self, bunch: DecisionBunch) -> list:
        """Parse received answers and return in correct order."""
        answers = []

        for i, decision in enumerate(bunch):
            key = decision.global_key or f"decision_{i}"

            if key in self.received_answers:
                raw_answer = self.received_answers[key]

                # Handle skipped decisions (null from frontend)
                if raw_answer is None:
                    if decision.allow_skip and decision.default is not None:
                        logger.info(f"Decision {key} skipped, using default: {decision.default}")
                        answers.append(decision.default)
                    elif decision.allow_skip:
                        logger.info(f"Decision {key} skipped, no default available")
                        answers.append(None)
                    else:
                        logger.warning(f"Decision {key} received null but skip not allowed, using default")
                        answers.append(decision.default)
                    continue

                # Handle empty string (unanswered) same as skip
                if isinstance(raw_answer, str) and raw_answer.strip() == '':
                    if decision.allow_skip:
                        logger.info(f"Decision {key} empty, treating as skip")
                        if decision.default is not None:
                            answers.append(decision.default)
                        else:
                            answers.append(None)
                    else:
                        logger.warning(f"Decision {key} empty but not skippable, using default")
                        answers.append(decision.default)
                    continue

                # Coerce web input types before parsing
                raw_answer = self._coerce_web_input(decision, raw_answer)
                parsed = self.parse(decision, raw_answer)
                answers.append(parsed)

            elif decision.default is not None:
                answers.append(decision.default)
            else:
                logger.warning(f"No answer for decision {key}, using None")
                answers.append(None)

        return answers

    @staticmethod
    def _coerce_web_input(decision, raw_answer):
        """Convert raw web input to the type expected by parse().

        HTML <select> elements always return strings, even for numeric
        indices. JSON may also deliver strings for numbers/bools depending
        on frontend handling. This method converts accordingly.
        """
        if raw_answer is None:
            return raw_answer

        if isinstance(decision, ListDecision):
            # Frontend sends the list index as string (e.g. "0", "2")
            if isinstance(raw_answer, str):
                try:
                    return int(raw_answer)
                except ValueError:
                    logger.warning(
                        f"Could not convert ListDecision answer "
                        f"'{raw_answer}' to int, passing as-is"
                    )
        elif isinstance(decision, RealDecision):
            # Ensure numeric type
            if isinstance(raw_answer, str):
                try:
                    return float(raw_answer)
                except ValueError:
                    logger.warning(
                        f"Could not convert RealDecision answer "
                        f"'{raw_answer}' to float, passing as-is"
                    )
            elif isinstance(raw_answer, int):
                return float(raw_answer)
        elif isinstance(decision, BoolDecision):
            # Handle string bools from JSON edge cases
            if isinstance(raw_answer, str):
                return raw_answer.lower() in ('true', '1', 'yes')

        return raw_answer

    def submit_answers(self, answers: Dict[str, Any]) -> bool:
        """
        Called by Flask server when frontend submits answers.

        Args:
            answers: Dict mapping decision IDs to answer values

        Returns:
            True if successful
        """
        if not self.is_waiting:
            logger.warning("submit_answers called but handler not waiting")
            return False

        self.received_answers = answers
        self.answer_event.set()

        logger.info(f"Received {len(answers)} answers")
        return True

    def get_pending_decisions(self) -> List[Dict[str, Any]]:
        """Get current pending decisions (for Flask API)."""
        if self.is_waiting:
            return self.pending_decisions_data
        return []

    def shutdown(self, success: bool):
        """Clean up handler."""
        self.is_waiting = False
        self.answer_event.set()  # Unblock if waiting
        WebGUIDecisionHandler._instance = None
        logger.info(f"WebGUIDecisionHandler shutdown (success={success})")
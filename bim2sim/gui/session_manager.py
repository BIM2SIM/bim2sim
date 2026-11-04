"""
Session Manager for bim2sim GUI.

Handles:
- Project configuration persistence
- Execution state storage
- Decision history tracking
- Session save/load/resume
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, asdict
import uuid

logger = logging.getLogger(__name__)


@dataclass
class SessionMetadata:
    """Metadata for a session."""
    session_id: str
    project_id: str
    project_name: str
    created_at: str
    updated_at: str
    status: str  # 'created', 'running', 'paused', 'finished', 'error'


class SessionManager:
    """Manages project sessions and their persistence."""

    def __init__(self, sessions_dir: Path = None):
        """
        Initialize Session Manager.

        Args:
            sessions_dir: Directory to store session files
        """
        if sessions_dir is None:
            # Default: user home directory
            sessions_dir = Path.home() / '.bim2sim' / 'sessions'

        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Session Manager initialized: {self.sessions_dir}")

    def create_session(
            self,
            project_id: str,
            project_name: str,
            project_config: Dict[str, Any]
    ) -> str:
        """
        Create a new session.

        Args:
            project_id: Unique project identifier
            project_name: Human-readable project name
            project_config: Project configuration dict

        Returns:
            session_id: Unique session identifier
        """
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        session_data = {
            'metadata': {
                'session_id': session_id,
                'project_id': project_id,
                'project_name': project_name,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'status': 'created'
            },
            'project_config': project_config,
            'execution_state': {
                'current_task': None,
                'completed_tasks': [],
                'pending_tasks': []
            },
            'decisions': {
                'made_decisions': [],
                'pending_decisions': []
            },
            'playground_state': None
        }

        self._save_session(session_id, session_data)
        logger.info(f"Created session: {session_id}")

        return session_id

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a session from disk.

        Args:
            session_id: Session identifier

        Returns:
            Session data dict or None if not found
        """
        session_file = self.sessions_dir / f"{session_id}.json"

        if not session_file.exists():
            logger.warning(f"Session not found: {session_id}")
            return None

        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)

            logger.info(f"Loaded session: {session_id}")
            return session_data

        except Exception as e:
            logger.error(f"Error loading session {session_id}: {e}")
            return None

    def save_session(
            self,
            session_id: str,
            session_data: Dict[str, Any],
            update_timestamp: bool = True
    ) -> bool:
        """
        Save session to disk.

        Args:
            session_id: Session identifier
            session_data: Complete session data
            update_timestamp: Update the updated_at timestamp

        Returns:
            Success status
        """
        if update_timestamp:
            session_data['metadata']['updated_at'] = datetime.now().isoformat()

        return self._save_session(session_id, session_data)

    def _save_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """Internal: Save session to disk."""
        session_file = self.sessions_dir / f"{session_id}.json"

        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved session: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving session {session_id}: {e}")
            return False

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session identifier

        Returns:
            Success status
        """
        session_file = self.sessions_dir / f"{session_id}.json"

        if not session_file.exists():
            logger.warning(f"Session not found for deletion: {session_id}")
            return False

        try:
            session_file.unlink()
            logger.info(f"Deleted session: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False

    def list_sessions(self, project_id: Optional[str] = None) -> List[SessionMetadata]:
        """
        List all sessions, optionally filtered by project.

        Args:
            project_id: Optional project filter

        Returns:
            List of session metadata
        """
        sessions = []

        for session_file in self.sessions_dir.glob("session_*.json"):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)

                metadata = session_data.get('metadata', {})

                # Filter by project if requested
                if project_id and metadata.get('project_id') != project_id:
                    continue

                sessions.append(SessionMetadata(**metadata))

            except Exception as e:
                logger.warning(f"Error reading session {session_file.name}: {e}")
                continue

        # Sort by updated_at (newest first)
        sessions.sort(key=lambda s: s.updated_at, reverse=True)

        return sessions

    def update_session_status(self, session_id: str, status: str) -> bool:
        """
        Update session status.

        Args:
            session_id: Session identifier
            status: New status ('running', 'paused', 'finished', 'error')

        Returns:
            Success status
        """
        session_data = self.load_session(session_id)

        if not session_data:
            return False

        session_data['metadata']['status'] = status
        return self.save_session(session_id, session_data)

    def add_decision(
            self,
            session_id: str,
            decision: Dict[str, Any],
            is_pending: bool = True
    ) -> bool:
        """
        Add a decision to the session.

        Args:
            session_id: Session identifier
            decision: Decision data
            is_pending: Whether decision is pending or made

        Returns:
            Success status
        """
        session_data = self.load_session(session_id)

        if not session_data:
            return False

        key = 'pending_decisions' if is_pending else 'made_decisions'
        session_data['decisions'][key].append(decision)

        return self.save_session(session_id, session_data)

    def move_decision_to_made(
            self,
            session_id: str,
            decision_id: str,
            answer: Any
    ) -> bool:
        """
        Move a decision from pending to made with answer.

        Args:
            session_id: Session identifier
            decision_id: Decision identifier
            answer: User's answer

        Returns:
            Success status
        """
        session_data = self.load_session(session_id)

        if not session_data:
            return False

        # Find and remove from pending
        pending = session_data['decisions']['pending_decisions']
        decision = None

        for i, d in enumerate(pending):
            if d.get('decision_id') == decision_id:
                decision = pending.pop(i)
                break

        if not decision:
            logger.warning(f"Decision {decision_id} not found in pending")
            return False

        # Add to made decisions with answer
        decision['answer'] = answer
        decision['timestamp'] = datetime.now().isoformat()
        session_data['decisions']['made_decisions'].append(decision)

        return self.save_session(session_id, session_data)

    def update_execution_state(
            self,
            session_id: str,
            current_task: Optional[str] = None,
            completed_task: Optional[str] = None
    ) -> bool:
        """
        Update execution state of session.

        Args:
            session_id: Session identifier
            current_task: Current task being executed
            completed_task: Task that was just completed

        Returns:
            Success status
        """
        session_data = self.load_session(session_id)

        if not session_data:
            return False

        if current_task:
            session_data['execution_state']['current_task'] = current_task

        if completed_task:
            if completed_task not in session_data['execution_state']['completed_tasks']:
                session_data['execution_state']['completed_tasks'].append(completed_task)

        return self.save_session(session_id, session_data)

    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of a session (metadata + stats).

        Args:
            session_id: Session identifier

        Returns:
            Summary dict or None
        """
        session_data = self.load_session(session_id)

        if not session_data:
            return None

        decisions = session_data.get('decisions', {})
        execution = session_data.get('execution_state', {})

        return {
            'metadata': session_data['metadata'],
            'stats': {
                'pending_decisions': len(decisions.get('pending_decisions', [])),
                'made_decisions': len(decisions.get('made_decisions', [])),
                'completed_tasks': len(execution.get('completed_tasks', [])),
                'current_task': execution.get('current_task')
            }
        }
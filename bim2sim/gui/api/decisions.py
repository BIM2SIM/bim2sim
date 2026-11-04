"""
Decision management API endpoints.

Handles:
- Getting pending decisions
- Submitting answers
"""

import logging
from flask import request, jsonify

from . import api_bp

logger = logging.getLogger(__name__)


@api_bp.route('/decisions', methods=['GET'])
def get_decisions():
    """Get current pending decisions."""
    try:
        from bim2sim.kernel.decision.webgui_decisionhandler import WebGUIDecisionHandler

        handler = WebGUIDecisionHandler.get_instance()

        if not handler:
            return jsonify({
                'pending': False,
                'decisions': [],
                'message': 'No active decision handler'
            })

        decisions = handler.get_pending_decisions()

        # Safety: verify JSON-serializability before jsonify
        import json
        try:
            json.dumps(decisions)
        except (TypeError, ValueError) as json_err:
            logger.error(f"Decisions data not JSON-serializable: {json_err}")
            # Force safe serialization via handler
            decisions = handler._safe_json(decisions)

        return jsonify({
            'pending': len(decisions) > 0,
            'decisions': decisions,
            'count': len(decisions)
        })

    except Exception as e:
        logger.error(f"Error getting decisions: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@api_bp.route('/decisions/answer', methods=['POST'])
def submit_answers():
    """Submit answers for pending decisions."""
    try:
        from bim2sim.kernel.decision.webgui_decisionhandler import WebGUIDecisionHandler
        
        handler = WebGUIDecisionHandler.get_instance()
        
        if not handler:
            return jsonify({'error': 'No active decision handler'}), 400
        
        data = request.get_json()
        
        if not data or 'answers' not in data:
            return jsonify({'error': 'Missing answers in request'}), 400
        
        answers = data['answers']
        success = handler.submit_answers(answers)
        
        if success:
            return jsonify({'message': 'Answers submitted successfully'})
        else:
            return jsonify({'error': 'Handler not waiting for answers'}), 400

    except Exception as e:
        logger.error(f"Error submitting answers: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/decisions/skip', methods=['POST'])
def skip_decision():
    """Skip a specific decision."""
    try:
        from bim2sim.kernel.decision.webgui_decisionhandler import WebGUIDecisionHandler
        
        handler = WebGUIDecisionHandler.get_instance()
        
        if not handler:
            return jsonify({'error': 'No active decision handler'}), 400
        
        data = request.get_json()
        decision_id = data.get('decision_id')
        
        if not decision_id:
            return jsonify({'error': 'Missing decision_id'}), 400
        
        # Submit None as answer for this decision (skip)
        answers = {decision_id: None}
        success = handler.submit_answers(answers)
        
        if success:
            return jsonify({'message': f'Decision {decision_id} skipped'})
        else:
            return jsonify({'error': 'Handler not waiting for answers'}), 400

    except Exception as e:
        logger.error(f"Error skipping decision: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/decisions/debug', methods=['GET'])
def debug_decisions():
    """Debug endpoint to check handler status."""
    try:
        from bim2sim.kernel.decision.webgui_decisionhandler import WebGUIDecisionHandler

        handler = WebGUIDecisionHandler.get_instance()

        debug_info = {
            'handler_exists': handler is not None,
            'handler_class': str(type(handler)) if handler else None,
            'is_waiting': handler.is_waiting if handler else None,
            'pending_count': len(handler.pending_decisions_data) if handler else 0,
            'has_pending_bunch': handler.pending_bunch is not None if handler else False,
        }

        return jsonify(debug_info)

    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}")
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500
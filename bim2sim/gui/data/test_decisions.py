"""
Test script for decision workflow.

Usage:
    python test_decisions.py [project_id]
"""

import sys
import time
import requests
import json

BASE_URL = "http://localhost:8080"


def execute_project(project_id):
    """Execute a project."""
    print(f"\nExecuting project: {project_id}")
    response = requests.post(f"{BASE_URL}/api/projects/{project_id}/execute")

    if response.status_code == 200:
        print(f"✓ Project execution started")
        print(f"  Response: {response.json()}")
        return True
    else:
        print(f"✗ Error: {response.status_code}")
        print(f"  {response.text}")
        return False


def poll_decisions(max_attempts=30, interval=2):
    """Poll for decisions with retry."""
    print(f"\nPolling for decisions (max {max_attempts} attempts, {interval}s interval)...")

    for attempt in range(1, max_attempts + 1):
        print(f"\nAttempt {attempt}/{max_attempts}:")

        try:
            response = requests.get(f"{BASE_URL}/api/decisions")
            data = response.json()

            print(f"  Status: {response.status_code}")
            print(f"  Pending: {data.get('pending', False)}")
            print(f"  Count: {data.get('count', 0)}")

            if data.get('pending', False) and data.get('count', 0) > 0:
                print(f"\n✓ Decisions available!")
                return data['decisions']

            if 'message' in data:
                print(f"  Message: {data['message']}")

        except Exception as e:
            print(f"  Error: {e}")

        if attempt < max_attempts:
            print(f"  Waiting {interval}s...")
            time.sleep(interval)

    print(f"\n✗ No decisions received after {max_attempts} attempts")
    return None


def display_decisions(decisions):
    """Display decisions in readable format."""
    print(f"\n{'=' * 60}")
    print(f"DECISIONS ({len(decisions)})")
    print(f"{'=' * 60}")

    for i, decision in enumerate(decisions):
        print(f"\nDecision {i + 1}:")
        print(f"  ID: {decision.get('id')}")
        print(f"  Type: {decision.get('type')}")
        print(f"  Question: {decision.get('question')}")

        if 'options' in decision and decision['options']:
            print(f"  Options:")
            for j, option in enumerate(decision['options']):
                print(f"    {j}: {option}")

        if decision.get('default') is not None:
            print(f"  Default: {decision.get('default')}")

        print(f"  Allow Skip: {decision.get('allow_skip', False)}")


def submit_answers(answers):
    """Submit answers to decisions."""
    print(f"\nSubmitting answers...")
    print(f"  Answers: {answers}")

    try:
        response = requests.post(
            f"{BASE_URL}/api/decisions/answer",
            json={'answers': answers},
            headers={'Content-Type': 'application/json'}
        )

        print(f"  Status: {response.status_code}")

        if response.status_code == 200:
            print(f"✓ Answers submitted successfully")
            print(f"  Response: {response.json()}")
            return True
        else:
            print(f"✗ Error submitting answers")
            print(f"  {response.text}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def interactive_answer(decisions):
    """Interactively answer decisions."""
    answers = {}

    for decision in decisions:
        decision_id = decision['id']
        question = decision['question']
        decision_type = decision['type']

        print(f"\n{'=' * 60}")
        print(f"Question: {question}")
        print(f"Type: {decision_type}")

        if decision_type == 'DecisionList':
            options = decision.get('options', [])
            print("\nOptions:")
            for i, option in enumerate(options):
                print(f"  {i}: {option}")

            while True:
                try:
                    answer = input(f"\nSelect option (0-{len(options) - 1}): ")
                    answer_int = int(answer)
                    if 0 <= answer_int < len(options):
                        answers[decision_id] = answer_int
                        break
                    else:
                        print(f"Invalid option. Must be 0-{len(options) - 1}")
                except ValueError:
                    print("Invalid input. Please enter a number.")

        elif decision_type == 'DecisionBool':
            while True:
                answer = input("\nAnswer (y/n): ").lower()
                if answer in ['y', 'yes', 'true', '1']:
                    answers[decision_id] = True
                    break
                elif answer in ['n', 'no', 'false', '0']:
                    answers[decision_id] = False
                    break
                else:
                    print("Invalid input. Please enter y or n.")

        elif decision_type == 'DecisionReal':
            while True:
                try:
                    answer = input("\nEnter number: ")
                    answers[decision_id] = float(answer)
                    break
                except ValueError:
                    print("Invalid input. Please enter a number.")

        elif decision_type == 'DecisionString':
            answer = input("\nEnter text: ")
            answers[decision_id] = answer

        else:
            print(f"Unknown decision type: {decision_type}")
            answer = input("\nEnter value: ")
            answers[decision_id] = answer

    return answers


def main():
    """Main test workflow."""
    if len(sys.argv) > 1:
        project_id = sys.argv[1]
    else:
        project_id = "example_hvac_aixlib"

    print(f"{'=' * 60}")
    print(f"DECISION WORKFLOW TEST")
    print(f"{'=' * 60}")
    print(f"Project: {project_id}")

    # Step 1: Execute project
    if not execute_project(project_id):
        return

    # Step 2: Poll for decisions
    decisions = poll_decisions(max_attempts=30, interval=2)

    if not decisions:
        print("\n✗ No decisions received. Check server logs.")
        return

    # Step 3: Display decisions
    display_decisions(decisions)

    # Step 4: Interactive answering
    print(f"\n{'=' * 60}")
    print("ANSWER DECISIONS")
    print(f"{'=' * 60}")

    answers = interactive_answer(decisions)

    # Step 5: Submit answers
    if submit_answers(answers):
        print("\n✓ Workflow completed!")
        print("\nYou can run this script again to handle the next DecisionBunch.")
    else:
        print("\n✗ Failed to submit answers")


if __name__ == '__main__':
    main()
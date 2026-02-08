"""
Test Browser Session Intent Normalization

Tests for the interpreter's browser session awareness:
1. Browser + navigation = collapse to browser.navigate
2. Browser + search = collapse to browser.search  
3. Standalone browser = app.launch (no collapse)
4. Browser + non-browser = independent_multi (no collapse)

Also tests the diagnostic warning in GoalOrchestrator.
"""

import pytest
import logging
from unittest.mock import patch, MagicMock

from agents.goal_interpreter import GoalInterpreter, Goal, MetaGoal


class TestBrowserSessionIntentNormalization:
    """Tests that browser session awareness examples work correctly."""
    
    @pytest.fixture
    def interpreter(self):
        """Create a GoalInterpreter for testing."""
        with patch('agents.goal_interpreter.get_model_manager') as mock_mm:
            mock_model = MagicMock()
            mock_mm.return_value.get.return_value = mock_model
            return GoalInterpreter()
    
    def test_browser_collapse_examples_in_prompt(self, interpreter):
        """Verify browser collapse examples are present in few-shot examples."""
        examples = interpreter.FEW_SHOT_EXAMPLES
        
        # Check for contextual intent resolution section
        assert "CONTEXTUAL INTENT RESOLUTION" in examples
        
        # Check for intent-focused reasoning (not implementation-focused)
        assert "User intent is" in examples
        assert "instrumental, not the goal" in examples
        
        # Check for collapse example
        assert "open chrome and go to youtube" in examples
        assert '"domain": "browser"' in examples
        assert '"verb": "navigate"' in examples
        
        # Check for terminal intent collapse example  
        assert "open chrome, go to youtube, search nvidia" in examples
        assert '"verb": "search"' in examples
        assert '"platform": "youtube"' in examples
        
        # Check for standalone browser = app.launch
        assert "User wants the Chrome window visible" in examples
        
    def test_example_teaches_intent_not_mechanics(self, interpreter):
        """Verify examples teach intent resolution, not mechanical collapse."""
        examples = interpreter.FEW_SHOT_EXAMPLES
        
        # Should NOT have implementation-focused reasoning
        assert "Browser session bootstraps" not in examples
        assert "Collapse to terminal intent" not in examples
        
        # SHOULD have intent-focused reasoning
        assert "User intent is to visit" in examples
        assert "User intent is to search" in examples


class TestBrowserLaunchDiagnosticWarning:
    """Tests for the _warn_if_browser_launch_with_browser_goals diagnostic."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create a GoalOrchestrator for testing."""
        with patch('agents.goal_orchestrator.GoalPlanner'):
            from agents.goal_orchestrator import GoalOrchestrator
            return GoalOrchestrator()
    
    def test_warning_triggered_for_browser_launch_with_browser_goals(self, orchestrator, caplog):
        """Warning should fire when app.launch(chrome) appears with browser goals."""
        # Create a problematic MetaGoal (app.launch + browser.navigate)
        goals = (
            Goal(domain="app", verb="launch", params={"app_name": "chrome"}, scope="root"),
            Goal(domain="browser", verb="navigate", params={"url": "https://youtube.com"}, scope="root"),
        )
        meta_goal = MetaGoal(meta_type="dependent_multi", goals=goals, dependencies=())
        
        with caplog.at_level(logging.WARNING):
            orchestrator._warn_if_browser_launch_with_browser_goals(meta_goal)
        
        assert "INTERPRETER_EXAMPLE_GAP" in caplog.text
        assert "app.launch(chrome)" in caplog.text
    
    def test_no_warning_for_standalone_browser_launch(self, orchestrator, caplog):
        """No warning for standalone app.launch(chrome) - this is correct."""
        goals = (
            Goal(domain="app", verb="launch", params={"app_name": "chrome"}, scope="root"),
        )
        meta_goal = MetaGoal(meta_type="single", goals=goals, dependencies=())
        
        with caplog.at_level(logging.WARNING):
            orchestrator._warn_if_browser_launch_with_browser_goals(meta_goal)
        
        assert "INTERPRETER_EXAMPLE_GAP" not in caplog.text
    
    def test_no_warning_for_browser_only_goals(self, orchestrator, caplog):
        """No warning when only browser domain goals present - this is correct."""
        goals = (
            Goal(domain="browser", verb="navigate", params={"url": "https://youtube.com"}, scope="root"),
            Goal(domain="browser", verb="search", params={"query": "nvidia"}, scope="root"),
        )
        meta_goal = MetaGoal(meta_type="dependent_multi", goals=goals, dependencies=())
        
        with caplog.at_level(logging.WARNING):
            orchestrator._warn_if_browser_launch_with_browser_goals(meta_goal)
        
        assert "INTERPRETER_EXAMPLE_GAP" not in caplog.text
    
    def test_no_warning_for_non_browser_app_with_browser_goals(self, orchestrator, caplog):
        """No warning when app.launch(non-browser) with browser goals."""
        # This is a valid case - user wants to open Spotify AND do browser stuff
        goals = (
            Goal(domain="app", verb="launch", params={"app_name": "spotify"}, scope="root"),
            Goal(domain="browser", verb="navigate", params={"url": "https://youtube.com"}, scope="root"),
        )
        meta_goal = MetaGoal(meta_type="independent_multi", goals=goals, dependencies=())
        
        with caplog.at_level(logging.WARNING):
            orchestrator._warn_if_browser_launch_with_browser_goals(meta_goal)
        
        assert "INTERPRETER_EXAMPLE_GAP" not in caplog.text
    
    def test_warning_for_various_browser_apps(self, orchestrator, caplog):
        """Warning should fire for any common browser app name."""
        browser_apps = ["chrome", "firefox", "edge", "brave", "opera"]
        
        for browser in browser_apps:
            caplog.clear()
            goals = (
                Goal(domain="app", verb="launch", params={"app_name": browser}, scope="root"),
                Goal(domain="browser", verb="search", params={"query": "test"}, scope="root"),
            )
            meta_goal = MetaGoal(meta_type="dependent_multi", goals=goals, dependencies=())
            
            with caplog.at_level(logging.WARNING):
                orchestrator._warn_if_browser_launch_with_browser_goals(meta_goal)
            
            assert "INTERPRETER_EXAMPLE_GAP" in caplog.text, f"Warning not triggered for {browser}"


class TestBrowserCollapsePatterns:
    """Tests for expected interpreter output patterns (requires LLM mocking)."""
    
    @pytest.fixture
    def mock_interpreter(self):
        """Create an interpreter with mocked LLM."""
        with patch('agents.goal_interpreter.get_model_manager') as mock_mm:
            mock_model = MagicMock()
            mock_mm.return_value.get.return_value = mock_model
            interpreter = GoalInterpreter()
            return interpreter, mock_model
    
    def test_expected_output_for_chrome_youtube_search(self, mock_interpreter):
        """For 'open chrome, go to youtube, search nvidia', expect single browser.search goal."""
        interpreter, mock_model = mock_interpreter
        
        # Mock the LLM to return the expected collapsed output
        # (This tests that IF the LLM follows examples, the result is correct)
        expected_response = {
            "meta_type": "single",
            "goals": [
                {
                    "domain": "browser",
                    "verb": "search",
                    "params": {"platform": "youtube", "query": "nvidia"},
                    "scope": "root"
                }
            ],
            "reasoning": "All browser operations. Collapse to terminal intent."
        }
        mock_model.generate.return_value = expected_response
        
        result = interpreter.interpret("open chrome, go to youtube, search nvidia")
        
        assert result.meta_type == "single"
        assert len(result.goals) == 1
        assert result.goals[0].domain == "browser"
        assert result.goals[0].verb == "search"
    
    def test_standalone_chrome_stays_app_launch(self, mock_interpreter):
        """For standalone 'open chrome', expect app.launch goal."""
        interpreter, mock_model = mock_interpreter
        
        expected_response = {
            "meta_type": "single",
            "goals": [
                {
                    "domain": "app",
                    "verb": "launch",
                    "params": {"app_name": "chrome"},
                    "scope": "root"
                }
            ],
            "reasoning": "Standalone app launch"
        }
        mock_model.generate.return_value = expected_response
        
        result = interpreter.interpret("open chrome")
        
        assert result.meta_type == "single"
        assert len(result.goals) == 1
        assert result.goals[0].domain == "app"
        assert result.goals[0].verb == "launch"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

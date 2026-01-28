"""Unit Tests for Phase 2B' Window Management Tools

Tests tool schemas, properties, and basic execution patterns.
Mock-based to avoid actual system changes during testing.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestWindowToolSchemas:
    """Test that all window tools have correct schemas and properties"""
    
    def test_minimize_all_properties(self):
        """Test MinimizeAll tool properties"""
        from tools.system.window.minimize_all import MinimizeAll
        tool = MinimizeAll()
        
        assert tool.name == "system.window.minimize_all"
        assert tool.risk_level == "low"
        assert tool.stabilization_time_ms == 200
        assert tool.requires_focus == False
        assert tool.requires_unlocked_screen == True
        assert "window_state_changed" in tool.side_effects
    
    def test_snap_left_properties(self):
        """Test SnapLeft tool properties"""
        from tools.system.window.snap_left import SnapLeft
        tool = SnapLeft()
        
        assert tool.name == "system.window.snap_left"
        assert tool.stabilization_time_ms == 150
        assert tool.requires_focus == True  # Needs window to snap
    
    def test_snap_right_properties(self):
        """Test SnapRight tool properties"""
        from tools.system.window.snap_right import SnapRight
        tool = SnapRight()
        
        assert tool.name == "system.window.snap_right"
        assert tool.stabilization_time_ms == 150
        assert tool.requires_focus == True
    
    def test_maximize_properties(self):
        """Test Maximize tool properties"""
        from tools.system.window.maximize import Maximize
        tool = Maximize()
        
        assert tool.name == "system.window.maximize"
        assert tool.stabilization_time_ms == 150
    
    def test_minimize_properties(self):
        """Test Minimize tool properties"""
        from tools.system.window.minimize import Minimize
        tool = Minimize()
        
        assert tool.name == "system.window.minimize"
        assert tool.stabilization_time_ms == 150
    
    def test_task_view_properties(self):
        """Test TaskView tool properties"""
        from tools.system.window.task_view import TaskView
        tool = TaskView()
        
        assert tool.name == "system.window.task_view"
        assert tool.stabilization_time_ms == 300  # Longer animation
        assert tool.requires_focus == False
    
    def test_close_properties(self):
        """Test Close tool properties"""
        from tools.system.window.close import Close
        tool = Close()
        
        assert tool.name == "system.window.close"
        assert tool.risk_level == "medium"  # Can lose unsaved work
        assert tool.stabilization_time_ms == 200
        assert "potential_data_loss" in tool.side_effects
    
    def test_switch_properties(self):
        """Test Switch tool properties - CRITICAL SAFETY"""
        from tools.system.window.switch import Switch
        tool = Switch()
        
        assert tool.name == "system.window.switch"
        assert tool.risk_level == "medium"
        assert tool.stabilization_time_ms == 300
        assert tool.requires_unlocked_screen == True


class TestDesktopToolSchemas:
    """Test that all desktop tools have correct schemas and properties"""
    
    def test_toggle_icons_properties(self):
        """Test ToggleIcons tool properties"""
        from tools.system.desktop.toggle_icons import ToggleIcons
        tool = ToggleIcons()
        
        assert tool.name == "system.desktop.toggle_icons"
        assert tool.risk_level == "low"
    
    def test_set_night_light_schema(self):
        """Test SetNightLight has enabled bool schema (idempotent)"""
        from tools.system.desktop.set_night_light import SetNightLight
        tool = SetNightLight()
        
        assert tool.name == "system.desktop.set_night_light"
        assert "enabled" in tool.schema["properties"]
        assert tool.schema["properties"]["enabled"]["type"] == "boolean"
        assert "enabled" in tool.schema["required"]
    
    def test_restart_explorer_properties(self):
        """Test RestartExplorer returns cooldown"""
        from tools.system.desktop.restart_explorer import RestartExplorer
        tool = RestartExplorer()
        
        assert tool.name == "system.desktop.restart_explorer"
        assert tool.risk_level == "medium"
        assert tool.stabilization_time_ms == 2000
    
    def test_empty_recycle_bin_confirmation_gate(self):
        """Test EmptyRecycleBin requires confirm=true"""
        from tools.system.desktop.empty_recycle_bin import EmptyRecycleBin
        tool = EmptyRecycleBin()
        
        assert tool.name == "system.desktop.empty_recycle_bin"
        assert tool.risk_level == "high"
        assert "confirm" in tool.schema["properties"]
        assert tool.schema["properties"]["confirm"]["type"] == "boolean"
        assert "confirm" in tool.schema["required"]
        assert tool.reversible == False
    
    def test_empty_recycle_bin_blocks_without_confirm(self):
        """Test that EmptyRecycleBin refuses without confirm=true"""
        from tools.system.desktop.empty_recycle_bin import EmptyRecycleBin
        tool = EmptyRecycleBin()
        
        # No confirm
        result = tool.execute({})
        assert result["status"] == "refused"
        
        # confirm=False
        result = tool.execute({"confirm": False})
        assert result["status"] == "refused"
        
        # confirm=True would actually delete, so we skip that in unit tests


class TestNetworkToolSchemas:
    """Test network tool schemas"""
    
    def test_set_airplane_mode_schema(self):
        """Test SetAirplaneMode has enabled bool schema (idempotent)"""
        from tools.system.network.set_airplane_mode import SetAirplaneMode
        tool = SetAirplaneMode()
        
        assert tool.name == "system.network.set_airplane_mode"
        assert "enabled" in tool.schema["properties"]
        assert tool.schema["properties"]["enabled"]["type"] == "boolean"
        assert "enabled" in tool.schema["required"]


class TestVirtualDesktopToolSchemas:
    """Test virtual desktop tool schemas"""
    
    def test_get_current_properties(self):
        """Test GetCurrentDesktop properties"""
        from tools.system.virtual_desktop.get_current import GetCurrentDesktop
        tool = GetCurrentDesktop()
        
        assert tool.name == "system.virtual_desktop.get_current"
        assert tool.risk_level == "low"
        assert tool.side_effects == []  # Read-only
    
    def test_switch_desktop_schema(self):
        """Test SwitchDesktop has desktop_number schema"""
        from tools.system.virtual_desktop.switch_desktop import SwitchDesktop
        tool = SwitchDesktop()
        
        assert tool.name == "system.virtual_desktop.switch"
        assert "desktop_number" in tool.schema["properties"]
        assert tool.schema["properties"]["desktop_number"]["type"] == "integer"
        assert tool.schema["properties"]["desktop_number"]["minimum"] == 1
    
    def test_move_window_schema(self):
        """Test MoveWindowToDesktop has window_title and desktop_number"""
        from tools.system.virtual_desktop.move_window_to_desktop import MoveWindowToDesktop
        tool = MoveWindowToDesktop()
        
        assert tool.name == "system.virtual_desktop.move_window_to_desktop"
        assert "window_title" in tool.schema["properties"]
        assert "desktop_number" in tool.schema["properties"]
        assert "window_title" in tool.schema["required"]
        assert "desktop_number" in tool.schema["required"]


class TestExecutorSafety:
    """Test executor Phase 2B' safety features"""
    
    def test_executor_has_pressed_keys(self):
        """Test ToolExecutor has pressed_keys set"""
        from execution.executor import ToolExecutor
        with patch('tools.registry.get_registry') as mock_registry:
            mock_registry.return_value = MagicMock()
            executor = ToolExecutor()
            
            assert hasattr(executor, 'pressed_keys')
            assert isinstance(executor.pressed_keys, set)
    
    def test_executor_has_cooldown(self):
        """Test ToolExecutor has cooldown_until"""
        from execution.executor import ToolExecutor
        with patch('tools.registry.get_registry') as mock_registry:
            mock_registry.return_value = MagicMock()
            executor = ToolExecutor()
            
            assert hasattr(executor, 'cooldown_until')
            assert executor.cooldown_until == 0.0
    
    def test_executor_has_release_method(self):
        """Test ToolExecutor has _release_all_keys method"""
        from execution.executor import ToolExecutor
        with patch('tools.registry.get_registry') as mock_registry:
            mock_registry.return_value = MagicMock()
            executor = ToolExecutor()
            
            assert hasattr(executor, '_release_all_keys')
            assert callable(executor._release_all_keys)


class TestIntentAgentUpdate:
    """Test IntentAgent includes window_management"""
    
    def test_window_management_in_enum(self):
        """Test window_management is in intent enum"""
        from agents.intent_agent import IntentAgent
        
        schema = IntentAgent.INTENT_SCHEMA
        enum_values = schema["properties"]["intent"]["enum"]
        
        assert "window_management" in enum_values
    
    def test_window_management_examples_in_prompt(self):
        """Test window_management has few-shot examples"""
        from agents.intent_agent import IntentAgent
        
        examples = IntentAgent.FEW_SHOT_EXAMPLES
        
        assert "window_management" in examples
        assert "snap" in examples.lower()
        assert "minimize all" in examples.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

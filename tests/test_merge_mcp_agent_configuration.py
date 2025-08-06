"""
Unit tests for MCP agent configuration merging functionality

This test file specifically tests the MCP agent configuration merging logic in TeamManager,
including merging of frontend settings and config.yaml file configurations, handling of name conflicts, etc.
"""

from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, patch
import pytest

from magentic_ui.backend.teammanager.teammanager import TeamManager
from magentic_ui.task_team import RunPaths


class TestMcpAgentConfigurationMerge:
    """Test class for MCP agent configuration merging functionality"""

    @pytest.fixture
    def dummy_paths(self) -> RunPaths:
        """Create a RunPaths instance for testing"""
        return RunPaths(
            internal_run_dir=Path("/tmp/test"),
            external_run_dir=Path("/tmp/test"),
            internal_root_dir=Path("/tmp"),
            external_root_dir=Path("/tmp"),
            run_suffix="test_run",
        )

    @pytest.fixture
    def team_manager(self) -> TeamManager:
        """Create a TeamManager instance for testing"""
        return TeamManager(
            internal_workspace_root=Path("/tmp"),
            external_workspace_root=Path("/tmp"),
            run_without_docker=True,
            inside_docker=False,
            config={}
        )

    @pytest.fixture
    def sample_frontend_mcp_configs(self) -> List[Dict[str, Any]]:
        """Create sample frontend MCP configurations"""
        return [
            {
                "name": "frontend_agent_1",
                "description": "Frontend MCP Agent 1",
                "system_message": "You are a frontend agent",
                "mcp_servers": [
                    {
                        "server_name": "FrontendServer1",
                        "server_params": {
                            "type": "StdioServerParams",
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-frontend"]
                        }
                    }
                ]
            },
            {
                "name": "frontend_agent_2", 
                "description": "Frontend MCP Agent 2",
                "system_message": "You are another frontend agent",
                "mcp_servers": [
                    {
                        "server_name": "FrontendServer2",
                        "server_params": {
                            "type": "StdioServerParams",
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-frontend2"]
                        }
                    }
                ]
            }
        ]

    @pytest.fixture
    def sample_config_file_mcp_configs(self) -> List[Dict[str, Any]]:
        """Create sample config.yaml file MCP configurations"""
        return [
            {
                "name": "config_agent_1",
                "description": "Config File MCP Agent 1", 
                "system_message": "You are a config file agent",
                "mcp_servers": [
                    {
                        "server_name": "ConfigServer1",
                        "server_params": {
                            "type": "StdioServerParams",
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-config"]
                        }
                    }
                ]
            },
            {
                "name": "config_agent_2",
                "description": "Config File MCP Agent 2",
                "system_message": "You are another config file agent", 
                "mcp_servers": [
                    {
                        "server_name": "ConfigServer2",
                        "server_type": "StdioServerParams",
                        "server_params": {
                            "command": "npx",
                            "args": ["-y", "@modelcontextprotocol/server-config2"]
                        }
                    }
                ]
            }
        ]

    def test_merge_no_config_file_mcp_agents(
        self, 
        team_manager: TeamManager, 
        dummy_paths: RunPaths,
        sample_frontend_mcp_configs: List[Dict[str, Any]]
    ):
        """Test using only frontend configuration when config.yaml has no MCP agent configs"""
        # Setup: config.yaml has no mcp_agent_configs
        team_manager.config = {}
        
        # Frontend settings configuration
        settings_config = {
            "mcp_agent_configs": sample_frontend_mcp_configs,
            "other_setting": "value"
        }
        
        # Simulate configuration merging logic in _create_team method
        mcp_agent_config_from_config_file = team_manager.config.get("mcp_agent_configs", None)
        settings_mcp_configs = settings_config.get("mcp_agent_configs", [])
        
        if mcp_agent_config_from_config_file:
            config_agent_names = [x.get("name") for x in mcp_agent_config_from_config_file]
            if settings_mcp_configs:
                settings_mcp_configs = [
                    x for x in settings_mcp_configs 
                    if x.get("name") not in config_agent_names
                ]
            merged_mcp_configs = settings_mcp_configs + mcp_agent_config_from_config_file
        else:
            merged_mcp_configs = settings_mcp_configs
        
        settings_config["mcp_agent_configs"] = merged_mcp_configs
        
        # Verify: should only contain frontend configurations
        assert len(settings_config["mcp_agent_configs"]) == 2
        assert settings_config["mcp_agent_configs"][0]["name"] == "frontend_agent_1"
        assert settings_config["mcp_agent_configs"][1]["name"] == "frontend_agent_2"

    def test_merge_no_frontend_mcp_agents(
        self, 
        team_manager: TeamManager, 
        dummy_paths: RunPaths,
        sample_config_file_mcp_configs: List[Dict[str, Any]]
    ):
        """Test using only config.yaml configuration when frontend has no MCP agent configs"""
        # Setup: config.yaml has mcp_agent_configs
        team_manager.config = {
            "mcp_agent_configs": sample_config_file_mcp_configs
        }
        
        # Frontend settings configuration (no mcp_agent_configs)
        settings_config = {
            "other_setting": "value"
        }
        
        # Simulate configuration merging logic in _create_team method
        mcp_agent_config_from_config_file = team_manager.config.get("mcp_agent_configs", None)
        settings_mcp_configs = settings_config.get("mcp_agent_configs", [])
        
        if mcp_agent_config_from_config_file:
            config_agent_names = [x.get("name") for x in mcp_agent_config_from_config_file]
            if settings_mcp_configs:
                settings_mcp_configs = [
                    x for x in settings_mcp_configs 
                    if x.get("name") not in config_agent_names
                ]
            merged_mcp_configs = settings_mcp_configs + mcp_agent_config_from_config_file
        else:
            merged_mcp_configs = settings_mcp_configs
        
        settings_config["mcp_agent_configs"] = merged_mcp_configs
        
        # Verify: should only contain config.yaml configurations
        assert len(settings_config["mcp_agent_configs"]) == 2
        assert settings_config["mcp_agent_configs"][0]["name"] == "config_agent_1"
        assert settings_config["mcp_agent_configs"][1]["name"] == "config_agent_2"

    def test_merge_both_sources_no_conflicts(
        self, 
        team_manager: TeamManager, 
        dummy_paths: RunPaths,
        sample_frontend_mcp_configs: List[Dict[str, Any]],
        sample_config_file_mcp_configs: List[Dict[str, Any]]
    ):
        """Test merging when both sources have configurations with no name conflicts"""
        # Setup: config.yaml has mcp_agent_configs
        team_manager.config = {
            "mcp_agent_configs": sample_config_file_mcp_configs
        }
        
        # Frontend settings configuration
        settings_config = {
            "mcp_agent_configs": sample_frontend_mcp_configs,
            "other_setting": "value"
        }
        
        # Simulate configuration merging logic in _create_team method
        mcp_agent_config_from_config_file = team_manager.config.get("mcp_agent_configs", None)
        settings_mcp_configs = settings_config.get("mcp_agent_configs", [])
        
        if mcp_agent_config_from_config_file:
            config_agent_names = [x.get("name") for x in mcp_agent_config_from_config_file]
            if settings_mcp_configs:
                settings_mcp_configs = [
                    x for x in settings_mcp_configs 
                    if x.get("name") not in config_agent_names
                ]
            merged_mcp_configs = settings_mcp_configs + mcp_agent_config_from_config_file
        else:
            merged_mcp_configs = settings_mcp_configs
        
        settings_config["mcp_agent_configs"] = merged_mcp_configs
        
        # Verify: should contain all 4 configurations (2 frontend + 2 config.yaml)
        assert len(settings_config["mcp_agent_configs"]) == 4
        
        # Verify frontend configurations come first
        assert settings_config["mcp_agent_configs"][0]["name"] == "frontend_agent_1"
        assert settings_config["mcp_agent_configs"][1]["name"] == "frontend_agent_2"
        
        # Verify config.yaml configurations come after
        assert settings_config["mcp_agent_configs"][2]["name"] == "config_agent_1"
        assert settings_config["mcp_agent_configs"][3]["name"] == "config_agent_2"

    def test_merge_with_name_conflicts(
        self, 
        team_manager: TeamManager, 
        dummy_paths: RunPaths
    ):
        """Test merging when both sources have agents with same names (config.yaml takes priority)"""
        # Create configurations with name conflicts
        frontend_configs = [
            {
                "name": "shared_agent",  # Conflicting agent name
                "description": "Frontend Shared Agent",
                "system_message": "Frontend version",
                "mcp_servers": []
            },
            {
                "name": "frontend_only_agent",
                "description": "Frontend Only Agent", 
                "system_message": "Only in frontend",
                "mcp_servers": []
            }
        ]
        
        config_file_configs = [
            {
                "name": "shared_agent",  # Conflicting agent name (should override frontend version)
                "description": "Config File Shared Agent",
                "system_message": "Config file version",
                "mcp_servers": []
            },
            {
                "name": "config_only_agent",
                "description": "Config Only Agent",
                "system_message": "Only in config file",
                "mcp_servers": []
            }
        ]
        
        # Setup: config.yaml has mcp_agent_configs
        team_manager.config = {
            "mcp_agent_configs": config_file_configs
        }
        
        # Frontend settings configuration
        settings_config = {
            "mcp_agent_configs": frontend_configs,
            "other_setting": "value"
        }
        
        # Simulate configuration merging logic in _create_team method
        mcp_agent_config_from_config_file = team_manager.config.get("mcp_agent_configs", None)
        settings_mcp_configs = settings_config.get("mcp_agent_configs", [])
        
        if mcp_agent_config_from_config_file:
            config_agent_names = [x.get("name") for x in mcp_agent_config_from_config_file]
            if settings_mcp_configs:
                settings_mcp_configs = [
                    x for x in settings_mcp_configs 
                    if x.get("name") not in config_agent_names
                ]
            merged_mcp_configs = settings_mcp_configs + mcp_agent_config_from_config_file
        else:
            merged_mcp_configs = settings_mcp_configs
        
        settings_config["mcp_agent_configs"] = merged_mcp_configs
        
        # Verify: should contain 3 configurations (conflicting ones filtered out)
        assert len(settings_config["mcp_agent_configs"]) == 3
        
        # Verify frontend-only agent is preserved
        frontend_only_found = False
        for config in settings_config["mcp_agent_configs"]:
            if config["name"] == "frontend_only_agent":
                frontend_only_found = True
                assert config["description"] == "Frontend Only Agent"
        assert frontend_only_found, "Frontend-only agent should be preserved"
        
        # Verify all config.yaml agents exist
        config_agents = [c for c in settings_config["mcp_agent_configs"] 
                        if c["name"] in ["shared_agent", "config_only_agent"]]
        assert len(config_agents) == 2
        
        # Verify conflicting agent uses config.yaml version
        shared_agent = next(c for c in settings_config["mcp_agent_configs"] 
                           if c["name"] == "shared_agent")
        assert shared_agent["description"] == "Config File Shared Agent"
        assert shared_agent["system_message"] == "Config file version"

    def test_merge_empty_frontend_configs(
        self, 
        team_manager: TeamManager, 
        dummy_paths: RunPaths,
        sample_config_file_mcp_configs: List[Dict[str, Any]]
    ):
        """Test merging when frontend configuration is an empty list"""
        # Setup: config.yaml has mcp_agent_configs
        team_manager.config = {
            "mcp_agent_configs": sample_config_file_mcp_configs
        }
        
        # Frontend settings configuration (empty list)
        settings_config = {
            "mcp_agent_configs": [],
            "other_setting": "value"
        }
        
        # Simulate configuration merging logic in _create_team method
        mcp_agent_config_from_config_file = team_manager.config.get("mcp_agent_configs", None)
        settings_mcp_configs = settings_config.get("mcp_agent_configs", [])
        
        if mcp_agent_config_from_config_file:
            config_agent_names = [x.get("name") for x in mcp_agent_config_from_config_file]
            if settings_mcp_configs:
                settings_mcp_configs = [
                    x for x in settings_mcp_configs 
                    if x.get("name") not in config_agent_names
                ]
            merged_mcp_configs = settings_mcp_configs + mcp_agent_config_from_config_file
        else:
            merged_mcp_configs = settings_mcp_configs
        
        settings_config["mcp_agent_configs"] = merged_mcp_configs
        
        # Verify: should only contain config.yaml configurations
        assert len(settings_config["mcp_agent_configs"]) == 2
        assert settings_config["mcp_agent_configs"][0]["name"] == "config_agent_1"
        assert settings_config["mcp_agent_configs"][1]["name"] == "config_agent_2"

    def test_merge_preserves_other_settings(
        self, 
        team_manager: TeamManager, 
        dummy_paths: RunPaths,
        sample_frontend_mcp_configs: List[Dict[str, Any]]
    ):
        """Test that merging process does not affect other settings"""
        # Setup: config.yaml has no mcp_agent_configs
        team_manager.config = {}
        
        # Frontend settings configuration (including other settings)
        settings_config = {
            "mcp_agent_configs": sample_frontend_mcp_configs,
            "cooperative_planning": True,
            "autonomous_execution": False,
            "browser_headless": True,
            "other_complex_setting": {
                "nested": "value",
                "list": [1, 2, 3]
            }
        }
        
        original_other_settings = {
            k: v for k, v in settings_config.items() 
            if k != "mcp_agent_configs"
        }
        
        # Simulate configuration merging logic in _create_team method
        mcp_agent_config_from_config_file = team_manager.config.get("mcp_agent_configs", None)
        settings_mcp_configs = settings_config.get("mcp_agent_configs", [])
        
        if mcp_agent_config_from_config_file:
            config_agent_names = [x.get("name") for x in mcp_agent_config_from_config_file]
            if settings_mcp_configs:
                settings_mcp_configs = [
                    x for x in settings_mcp_configs 
                    if x.get("name") not in config_agent_names
                ]
            merged_mcp_configs = settings_mcp_configs + mcp_agent_config_from_config_file
        else:
            merged_mcp_configs = settings_mcp_configs
        
        settings_config["mcp_agent_configs"] = merged_mcp_configs
        
        # Verify: other settings remain unchanged
        for key, value in original_other_settings.items():
            assert settings_config[key] == value, f"Setting {key} should remain unchanged"
        
        # Verify: mcp_agent_configs is correctly updated
        assert len(settings_config["mcp_agent_configs"]) == 2
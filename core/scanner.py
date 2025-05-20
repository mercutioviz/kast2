#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# scanner.py
# Core scanner orchestration logic for KAST (Kali Automated Scan Tool)

import os
import importlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Type

from core.plugin_base import PluginBase, PluginStatus, ScanType

class ScanOrchestrator:
    """
    Manages the discovery, dependency resolution, and execution of scanning plugins.
    
    Responsibilities:
    - Discover available plugins
    - Resolve plugin dependencies
    - Manage concurrent and sequential plugin execution
    - Handle error scenarios
    """
    
    def __init__(self, target: str, output_dir: str, config: Dict = None):
        """
        Initialize the scan orchestrator.
        
        Args:
            target: The target URL or domain to scan
            output_dir: Directory to store scan results
            config: Optional configuration dictionary
        """
        self.target = target
        self.output_dir = output_dir
        self.config = config or {}
        self.logger = logging.getLogger("kast.scanner")
        
        # Discover and load plugins
        self.plugins = self._discover_plugins()
        
    def _discover_plugins(self) -> List[Type[PluginBase]]:
        """
        Dynamically discover and load plugins from the plugins directory.
        
        Returns:
            List of plugin classes
        """
        plugins = []
        plugins_dir = os.path.join(os.path.dirname(__file__), '..', 'plugins')
        
        for plugin_name in os.listdir(plugins_dir):
            plugin_path = os.path.join(plugins_dir, plugin_name)
            
            # Skip non-directories and __init__.py
            if not os.path.isdir(plugin_path) or plugin_name.startswith('__'):
                continue
            
            try:
                # Dynamically import the plugin module
                module = importlib.import_module(f'plugins.{plugin_name}.plugin')
                
                # Find and add plugin classes
                for name, obj in module.__dict__.items():
                    if (isinstance(obj, type) and 
                        issubclass(obj, PluginBase) and 
                        obj is not PluginBase):
                        plugins.append(obj)
                
            except ImportError as e:
                self.logger.error(f"Could not import plugin {plugin_name}: {e}")
        
        return plugins
    
    def _resolve_dependencies(self, plugins: List[Type[PluginBase]]) -> List[Type[PluginBase]]:
        """
        Resolve and order plugins based on their dependencies.
        
        Args:
            plugins: List of plugin classes to resolve
        
        Returns:
            Ordered list of plugins to execute
        """
        # Placeholder for more complex dependency resolution
        # For MVP, we'll sort plugins by scan type (passive first)
        return sorted(
            plugins, 
            key=lambda p: 0 if p.scan_type == ScanType.PASSIVE else 1
        )
    
    def run_scans(self, max_concurrent: int = 3) -> List[Dict]:
        """
        Execute all discovered plugins.
        
        Args:
            max_concurrent: Maximum number of concurrent plugin executions
        
        Returns:
            List of scan results
        """
        # Resolve plugin dependencies and order
        ordered_plugins = self._resolve_dependencies(self.plugins)
        
        # Results storage
        scan_results = []
        
        # Concurrent execution
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            # Submit plugin execution tasks
            future_to_plugin = {
                executor.submit(
                    self._execute_plugin, 
                    plugin_class(
                        target=self.target, 
                        output_dir=self.output_dir, 
                        config=self.config
                    )
                ): plugin_class for plugin_class in ordered_plugins
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_plugin):
                plugin_class = future_to_plugin[future]
                try:
                    result = future.result()
                    scan_results.append(result)
                except Exception as e:
                    self.logger.error(f"Plugin {plugin_class.__name__} failed: {e}")
        
        return scan_results
    
    def _execute_plugin(self, plugin_instance: PluginBase) -> Dict:
        """
        Execute a single plugin with error handling.
        
        Args:
            plugin_instance: Instantiated plugin to run
        
        Returns:
            Plugin execution results
        """
        try:
            # Check if plugin should run based on its run-if logic
            if not plugin_instance.run_if():
                self.logger.info(f"Plugin {plugin_instance.name} did not meet run conditions")
                return {
                    "plugin": plugin_instance.name,
                    "status": "Not Run",
                    "reason": "Run conditions not met"
                }
            
            # Run the plugin
            return plugin_instance.run()
        
        except Exception as e:
            self.logger.error(f"Error in plugin {plugin_instance.name}: {e}")
            return {
                "plugin": plugin_instance.name,
                "status": "Failed",
                "error": str(e)
            }
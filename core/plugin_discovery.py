#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# plugin_discovery.py
# Module for dynamically discovering and loading KAST plugins

import os
import importlib
import inspect
from typing import List, Type, Dict

from core.plugin_base import PluginBase

class PluginDiscoverer:
    """
    Handles the discovery and loading of plugins for the KAST framework.
    """
    
    def __init__(self, plugins_dir: str):
        """
        Initialize the plugin discoverer.
        
        Args:
            plugins_dir: Path to the directory containing plugins
        """
        self.plugins_dir = plugins_dir
        self.discovered_plugins: Dict[str, Type[PluginBase]] = {}
    
    def discover_plugins(self) -> List[Type[PluginBase]]:
        """
        Discover and load all available plugins.
        
        Returns:
            List of plugin classes that inherit from PluginBase
        """
        # Ensure the plugins directory exists
        if not os.path.exists(self.plugins_dir):
            raise FileNotFoundError(f"Plugins directory not found: {self.plugins_dir}")
        
        # Clear previous discoveries
        self.discovered_plugins.clear()
        
        # Walk through the plugins directory
        for root, dirs, files in os.walk(self.plugins_dir):
            for file in files:
                if file.endswith('plugin.py'):
                    # Construct the full path to the plugin file
                    full_path = os.path.join(root, file)
                    
                    # Convert path to module path
                    relative_path = os.path.relpath(full_path, os.path.dirname(self.plugins_dir))
                    module_path = relative_path.replace(os.path.sep, '.').replace('.py', '')
                    full_module_name = f'plugins.{module_path}'
                    
                    try:
                        # Import the module dynamically
                        module = importlib.import_module(full_module_name)
                        
                        # Find all classes in the module that are subclasses of PluginBase
                        for name, obj in inspect.getmembers(module):
                            if (inspect.isclass(obj) and 
                                issubclass(obj, PluginBase) and 
                                obj is not PluginBase):
                                
                                # Store the plugin class
                                self.discovered_plugins[name] = obj
                    
                    except ImportError as e:
                        print(f"Error importing plugin {full_module_name}: {e}")
                    except Exception as e:
                        print(f"Unexpected error discovering plugin {full_module_name}: {e}")
        
        return list(self.discovered_plugins.values())
    
    def get_plugin_by_name(self, name: str) -> Type[PluginBase]:
        """
        Retrieve a specific plugin by its name.
        
        Args:
            name: Name of the plugin class
        
        Returns:
            Plugin class
        
        Raises:
            KeyError if plugin not found
        """
        if name not in self.discovered_plugins:
            raise KeyError(f"Plugin {name} not found")
        
        return self.discovered_plugins[name]
    
    def get_all_plugin_names(self) -> List[str]:
        """
        Get names of all discovered plugins.
        
        Returns:
            List of plugin names
        """
        return list(self.discovered_plugins.keys())

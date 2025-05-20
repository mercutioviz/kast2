#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# plugin_base.py

import abc
import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Any

class ScanType(Enum):
    """Enum defining the types of scans a plugin can perform."""
    PASSIVE = "passive"  # Non-intrusive scans that don't actively probe the target
    ACTIVE = "active"    # Scans that actively probe the target system

class OutputMethod(Enum):
    """Enum defining how a plugin captures output."""
    STDOUT = "stdout"    # Tool outputs to standard output
    FILE = "file"        # Tool writes directly to a file

class PluginStatus(Enum):
    """Enum defining the status of a plugin execution."""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

class PluginBase(abc.ABC):
    """Base class for all KAST scanner plugins.
    
    All scanner plugins must inherit from this class and implement
    the required abstract methods.
    """
    
    def __init__(self, target: str, output_dir: str, config: Dict = None):
        """Initialize the plugin.
        
        Args:
            target: The target URL or domain to scan
            output_dir: Directory where output files should be stored
            config: Optional configuration dictionary for the plugin
        """
        self.target = target
        self.output_dir = output_dir
        self.config = config or {}
        self.logger = logging.getLogger(f"kast.plugins.{self.name}")
        self.status = PluginStatus.NOT_STARTED
        self.start_time = None
        self.end_time = None
        self.raw_output = None
        self.results = None
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Return the name of the plugin."""
        pass
    
    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Return a description of what the plugin does."""
        pass
    
    @property
    @abc.abstractmethod
    def scan_type(self) -> ScanType:
        """Return whether this is an active or passive scan."""
        pass
    
    @property
    @abc.abstractmethod
    def output_method(self) -> OutputMethod:
        """Return how this plugin captures output."""
        pass
    
    @property
    def version(self) -> str:
        """Return the version of the underlying tool."""
        return "unknown"
    
    @property
    def timeout(self) -> int:
        """Return the timeout in seconds for this plugin."""
        return self.config.get("timeout", 300)  # Default 5 minutes
    
    @property
    def niceness(self) -> int:
        """Return the niceness value for this plugin."""
        return self.config.get("niceness", 10)  # Default niceness
    
    @abc.abstractmethod
    def check_dependencies(self) -> bool:
        """Check if all dependencies for this plugin are installed.
        
        Returns:
            bool: True if all dependencies are met, False otherwise
        """
        pass
    
    @abc.abstractmethod
    def build_command(self) -> List[str]:
        """Build the command to execute the underlying tool.
        
        Returns:
            List[str]: Command and arguments as a list
        """
        pass
    
    @abc.abstractmethod
    def parse_output(self, raw_output: Union[str, bytes]) -> Dict:
        """Parse the raw output from the tool into a structured format.
        
        Args:
            raw_output: The raw output from the tool execution
            
        Returns:
            Dict: Structured results
        """
        pass
    
    def run(self) -> Dict:
        """Execute the plugin and return results.
        
        Returns:
            Dict: Scan results in a standardized format
        """
        if not self.check_dependencies():
            self.status = PluginStatus.FAILED
            self.logger.error(f"Dependencies not met for {self.name}")
            return self._format_results(error="Dependencies not met")
        
        self.status = PluginStatus.RUNNING
        self.start_time = datetime.utcnow()
        
        try:
            cmd = self.build_command()
            self.logger.info(f"Executing: {' '.join(cmd)}")
            
            # Handle different output methods
            if self.output_method == OutputMethod.STDOUT:
                # Capture output from stdout
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=False
                )
                self.raw_output = process.stdout
                stderr_output = process.stderr
                return_code = process.returncode
                
            elif self.output_method == OutputMethod.FILE:
                # Tool writes to file directly, create a temp file path
                output_file = os.path.join(self.output_dir, f"{self.name}_raw_output.json")
                
                # Add output file to command if needed
                if "{output_file}" in cmd:
                    cmd = [arg.replace("{output_file}", output_file) for arg in cmd]
                
                # Run the process
                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=False
                )
                
                stderr_output = process.stderr
                return_code = process.returncode
                
                # Read the output file if it exists
                if os.path.exists(output_file):
                    with open(output_file, 'r') as f:
                        self.raw_output = f.read()
                else:
                    self.raw_output = ""
            
            # Check for errors
            if return_code != 0:
                self.logger.warning(f"Process returned non-zero exit code: {return_code}")
                self.logger.warning(f"stderr: {stderr_output}")
            
            # Parse the output
            parsed_results = self.parse_output(self.raw_output)
            self.status = PluginStatus.COMPLETED
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"Plugin {self.name} timed out after {self.timeout} seconds")
            self.status = PluginStatus.TIMEOUT
            parsed_results = {}
        except Exception as e:
            self.logger.exception(f"Error running plugin {self.name}: {str(e)}")
            self.status = PluginStatus.FAILED
            parsed_results = {}
        
        self.end_time = datetime.utcnow()
        return self._format_results(parsed_results=parsed_results)
    
    def _format_results(self, parsed_results: Dict = None, error: str = None) -> Dict:
        """Format the results into a standardized structure.
        
        Args:
            parsed_results: The parsed results from the tool
            error: Optional error message
            
        Returns:
            Dict: Standardized results structure
        """
        self.results = {
            "tool_name": self.name,
            "tool_description": self.description,
            "tool_version": self.version,
            "scan_type": self.scan_type.value,
            "target": self.target,
            "timestamp_start": self.start_time.isoformat() if self.start_time else None,
            "timestamp_end": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else None,
            "status": self.status.value,
            "raw_output": self.raw_output,
            "findings": parsed_results or {},
        }
        
        if error:
            self.results["error"] = error
            
        # Save results to file
        results_file = os.path.join(self.output_dir, f"{self.name}_results.json")
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        return self.results
    
    def can_resume(self) -> bool:
        """Check if this plugin supports resuming interrupted scans.
        
        Returns:
            bool: True if the plugin supports resuming, False otherwise
        """
        return False
    
    def resume(self) -> Dict:
        """Resume an interrupted scan.
        
        Returns:
            Dict: Scan results
        """
        self.logger.warning(f"Resume not implemented for {self.name}")
        return self._format_results(error="Resume not supported")
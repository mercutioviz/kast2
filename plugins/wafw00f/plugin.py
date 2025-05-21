#!/usr/bin/env python3
# plugins/wafw00f/plugin.py

import json
import os
import subprocess
from typing import Dict, List

from core.plugin_base import PluginBase, ScanType, OutputMethod

class WafW00fPlugin(PluginBase):
    @property
    def name(self) -> str:
        return "wafw00f"
    
    @property
    def description(self) -> str:
        return "Web Application Firewall Detection Tool"
    
    @property
    def scan_type(self) -> ScanType:
        return ScanType.PASSIVE
    
    @property
    def output_method(self) -> OutputMethod:
        return OutputMethod.FILE
    
    def check_dependencies(self) -> bool:
        try:
            subprocess.run(["wafw00f", "--version"], 
                           capture_output=True, 
                           text=True, 
                           check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def build_command(self) -> List[str]:
        # Prepare base command
        cmd = ["wafw00f", "-f", "json"]
        
        # Prepare output file path
        output_file = os.path.join(self.output_dir, f"{self.name}_raw_output.json")
        cmd.extend(["-o", output_file])
        
        # Add target
        cmd.append(self.target)
        
        # Add verbose flag if specified in args
        if self.config.get('verbose', False):
            cmd.append("-v")
        
        return cmd
    
    def parse_output(self, raw_output: str) -> Dict:
        try:
            # Try to parse the JSON output
            output_file = os.path.join(self.output_dir, f"{self.name}_raw_output.json")
            with open(output_file, 'r') as f:
                data = json.load(f)
            
            # Extract key findings
            findings = {
                "detected_waf": data.get("firewall", "No WAF detected")
            }
            
            return findings
        except (json.JSONDecodeError, FileNotFoundError) as e:
            self.logger.error(f"Error parsing wafw00f output: {e}")
            return {}
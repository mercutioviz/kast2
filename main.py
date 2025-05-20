#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main.py - Main entry point for KAST (Kali Automated Scan Tool)

import argparse
import importlib
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Type

import rich
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table

from core.scanner import ScanOrchestrator
from config.config import ConfigManager
from core.plugin_base import PluginBase

class KASTCLIApp:
    def __init__(self):
        """Initialize the KAST CLI application."""
        # Setup Rich console for colorized output
        self.console = Console()
        
        # Setup Rich logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(rich_tracebacks=True, console=self.console)]
        )
        self.logger = logging.getLogger("KAST")

    def discover_plugins(self) -> List[Type[PluginBase]]:
        """
        Dynamically discover and load plugins from the plugins directory.
        
        Returns:
            List of plugin classes
        """
        plugins = []
        plugins_dir = Path(__file__).parent / 'plugins'
        
        try:
            for plugin_path in plugins_dir.iterdir():
                if plugin_path.is_dir() and (plugin_path / '__init__.py').exists():
                    module_name = f"plugins.{plugin_path.name}.plugin"
                    try:
                        module = importlib.import_module(module_name)
                        for name, obj in module.__dict__.items():
                            if (isinstance(obj, type) and 
                                issubclass(obj, PluginBase) and 
                                obj is not PluginBase):
                                plugins.append(obj)
                    except ImportError as e:
                        self.logger.error(f"Could not import plugin {plugin_path.name}: {e}")
        except Exception as e:
            self.logger.error(f"Error discovering plugins: {e}")
        
        return plugins

    def setup_argument_parser(self, plugins: List[Type[PluginBase]]) -> argparse.ArgumentParser:
        """
        Setup argument parser with dynamic plugin-specific arguments.
        
        Args:
            plugins: List of discovered plugin classes
        
        Returns:
            Configured ArgumentParser
        """
        parser = argparse.ArgumentParser(
            description="KAST: Kali Automated Scan Tool",
            formatter_class=argparse.RichHelpFormatter
        )
        
        # Core arguments
        parser.add_argument('target', help='Target URL or domain to scan')
        parser.add_argument('-o', '--output-dir', 
                            default='./kast_output', 
                            help='Directory to store scan results')
        parser.add_argument('--dry-run', 
                            action='store_true', 
                            help='Show what would be executed without running scans')
        parser.add_argument('--report-only', 
                            help='Generate report from previous scan results')
        
        # Plugin-specific arguments group
        plugin_group = parser.add_argument_group('Plugin Options')
        for plugin_cls in plugins:
            # If plugin has a class method to add CLI arguments, call it
            if hasattr(plugin_cls, 'add_arguments'):
                plugin_cls.add_arguments(plugin_group)
        
        return parser

    def run(self):
        """
        Main application entry point.
        """
        # Display banner
        self.console.print(Panel.fit(
            "[bold green]KAST - Kali Automated Scan Tool[/bold green]\n"
            "[dim]Automated Web Application Security Scanner[/dim]",
            border_style="bold blue"
        ))

        # Discover plugins
        plugins = self.discover_plugins()
        self.logger.info(f"Discovered {len(plugins)} plugins")

        # Setup argument parser
        parser = self.setup_argument_parser(plugins)
        args = parser.parse_args()

        # Create output directory
        os.makedirs(args.output_dir, exist_ok=True)

        # Initialize configuration
        config_manager = ConfigManager(args)

        # Initialize scanner orchestrator
        orchestrator = ScanOrchestrator(
            target=args.target,
            output_dir=args.output_dir,
            plugins=plugins,
            config=config_manager.get_config()
        )

        # Perform scan
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            scan_task = progress.add_task("[green]Running Scans...", total=100)
            
            try:
                results = orchestrator.run_scans()
                progress.update(scan_task, completed=100)
                
                # Display results summary
                self.display_results_summary(results)
                
            except Exception as e:
                self.logger.error(f"Scan failed: {e}")

    def display_results_summary(self, results: List[Dict]):
        """
        Display a rich, formatted summary of scan results.
        
        Args:
            results: List of scan results
        """
        table = Table(title="Scan Results Summary")
        table.add_column("Plugin", style="cyan")
        table.add_column("Status", style="magenta")
        table.add_column("Findings", style="green")
        
        for result in results:
            table.add_row(
                result.get('tool_name', 'Unknown'),
                result.get('status', 'N/A'),
                str(len(result.get('findings', {})))
            )
        
        self.console.print(table)

def main():
    try:
        app = KASTCLIApp()
        app.run()
    except KeyboardInterrupt:
        rich.print("[bold red]Scan interrupted by user.[/bold red]")
        sys.exit(1)

if __name__ == "__main__":
    main()
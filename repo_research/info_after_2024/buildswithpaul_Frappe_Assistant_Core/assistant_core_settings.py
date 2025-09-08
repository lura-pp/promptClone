# -*- coding: utf-8 -*-
# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import frappe
from frappe.model.document import Document
from frappe import _
from frappe_assistant_core.assistant_core.server import assistantServer

class AssistantCoreSettings(Document):
    """assistant Server Settings DocType controller"""
    
    def validate(self):
        """Validate settings before saving"""
        # Validate max connections
        if self.max_connections < 1 or self.max_connections > 1000:
            frappe.throw("Max connections must be between 1 and 1000")
        
        # Validate rate limit
        if self.rate_limit < 1 or self.rate_limit > 10000:
            frappe.throw("Rate limit must be between 1 and 10000 requests per minute")
        
        # Validate SSL settings
        if self.ssl_enabled:
            if not self.ssl_cert_path or not self.ssl_key_path:
                frappe.throw("SSL certificate and key paths are required when SSL is enabled")
    
    
    def restart_assistant_core(self):
        """Restart the assistant MCP API with new settings"""
        try:
            # Disable existing API
            self.disable_assistant_api()
            
            # Enable API with new settings
            self.enable_assistant_api()
            
            frappe.msgprint("assistant MCP API restarted successfully")
            
        except Exception as e:
            frappe.log_error(f"Failed to restart assistant MCP API: {str(e)}")
            frappe.throw(f"Failed to restart assistant MCP API: {str(e)}")
    
    def enable_assistant_api(self):
        """Enable the assistant MCP API"""
        try:
            server = assistantServer()
            server.enable()
            
            # Log the API enable (skip if DocType doesn't exist)
            try:
                if frappe.db.table_exists("tabAssistant Connection Log"):
                    frappe.get_doc({
                        "doctype": "Assistant Connection Log",
                        "action": "api_enabled",
                        "user": frappe.session.user,
                        "details": "assistant MCP API enabled"
                    }).insert(ignore_permissions=True)
            except:
                pass  # Don't fail API enable if logging fails
            
        except Exception as e:
            frappe.log_error(f"Failed to enable assistant MCP API: {str(e)}")
            raise
    
    def disable_assistant_api(self):
        """Disable the assistant MCP API"""
        try:
            server = assistantServer()
            server.disable()
            
            # Log the API disable (skip if DocType doesn't exist)
            try:
                if frappe.db.table_exists("tabAssistant Connection Log"):
                    frappe.get_doc({
                        "doctype": "Assistant Connection Log",
                        "action": "api_disabled",
                        "user": frappe.session.user,
                        "details": "assistant MCP API disabled"
                    }).insert(ignore_permissions=True)
            except:
                pass  # Don't fail API disable if logging fails
            
        except Exception as e:
            frappe.log_error(f"Failed to disable assistant MCP API: {str(e)}")
            raise
    
    # Legacy function names for backward compatibility
    def start_assistant_core(self):
        """Legacy: Enable the assistant MCP API"""
        return self.enable_assistant_api()
    
    def stop_assistant_core(self):
        """Legacy: Disable the assistant MCP API"""
        return self.disable_assistant_api()
    
    def get_streaming_protocol(self):
        """Get current streaming protocol configuration"""
        # Check if streaming-related fields exist in the DocType
        streaming_config = {
            "artifact_streaming_enforced": True,  # Default to enforced
            "protocol_status": "active",
            "limit_prevention_active": True,
            "streaming_behavior_instructions": """
Always create analysis workspace artifacts before performing data analysis.
Stream all detailed work to artifacts to prevent response limits.
Keep responses minimal with artifact references.
Build unlimited analysis depth via progressive artifact updates.
            """
        }
        
        # If fields exist in DocType, use their values
        if hasattr(self, "enforce_artifact_streaming"):
            streaming_config["artifact_streaming_enforced"] = self.enforce_artifact_streaming
            streaming_config["protocol_status"] = "active" if self.enforce_artifact_streaming else "optional"
        
        if hasattr(self, "response_limit_prevention"):
            streaming_config["limit_prevention_active"] = self.response_limit_prevention
            
        if hasattr(self, "streaming_behavior_instructions"):
            streaming_config["custom_instructions"] = self.streaming_behavior_instructions
        
        return streaming_config
    
    def get_enhanced_settings(self):
        """Get all settings including streaming protocol"""
        settings = self.as_dict()
        settings["streaming_protocol"] = self.get_streaming_protocol()
        return settings
    
    @frappe.whitelist()
    def refresh_plugins(self):
        """Refresh the entire plugin system - discovery and tools"""
        try:
            from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
            
            # Refresh plugin manager discovery
            plugin_manager = get_plugin_manager()
            plugin_manager.refresh_plugins()
            
            # Get statistics
            discovered_plugins = plugin_manager.get_discovered_plugins()
            enabled_plugins = plugin_manager.get_enabled_plugins()
            available_tools = plugin_manager.get_all_tools()
            
            frappe.msgprint(
                frappe._("Plugin system refreshed successfully.<br>Found {0} tools from {1} plugins.<br>Plugins: {2} enabled out of {3} discovered.").format(
                    len(available_tools),
                    len(enabled_plugins),
                    len(enabled_plugins),
                    len(discovered_plugins)
                )
            )
            
            return {
                "success": True,
                "stats": {
                    "total_tools": len(available_tools),
                    "discovered_plugins": len(discovered_plugins),
                    "enabled_plugins": len(enabled_plugins)
                }
            }
            
        except Exception as e:
            frappe.log_error(
                title=frappe._("Plugin Refresh Error"),
                message=str(e)
            )
            frappe.throw(
                frappe._("Failed to refresh plugin system: {0}").format(str(e))
            )
    
    
    def on_update(self):
        """Handle settings update"""
        from frappe_assistant_core.assistant_core.server import get_server_instance
        
        server = get_server_instance()
        server_was_enabled = self.has_value_changed('server_enabled')
        
        # Handle MCP API enable/disable
        if self.server_enabled:
            if server_was_enabled or not server.running:
                # Enable API if it was just enabled or not running
                frappe.enqueue('frappe_assistant_core.assistant_core.server.enable_background_api', queue='short')
        else:
            if server_was_enabled and server.running:
                # Disable API if it was just disabled
                self.disable_assistant_api()
        
        # Refresh tool registry if settings changed
        try:
            from frappe_assistant_core.utils.tool_cache import refresh_tool_cache
            refresh_tool_cache()
        except Exception as e:
            frappe.log_error(
                title=frappe._("Tool Cache Refresh Error"),
                message=str(e)
            )
    
    @frappe.whitelist()
    def get_plugin_status(self):
        """Get plugin status with enable/disable controls"""
        try:
            from frappe_assistant_core.utils.plugin_manager import get_plugin_manager
            
            # Get plugin manager for plugin info
            plugin_manager = get_plugin_manager()
            discovered_plugins = plugin_manager.get_discovered_plugins()
            enabled_plugins = plugin_manager.get_enabled_plugins()
            available_tools = plugin_manager.get_all_tools()
            
            # Build HTML with plugin controls
            html_parts = []
            
            # Overall statistics header
            html_parts.append(f"""
            <div class="alert alert-info mb-3">
                <h5><i class="fa fa-cogs"></i> Plugin System Status</h5>
                <div class="row">
                    <div class="col-md-4"><strong>Total Tools:</strong> {len(available_tools)}</div>
                    <div class="col-md-4"><strong>Active Plugins:</strong> {len(enabled_plugins)}/{len(discovered_plugins)}</div>
                    <div class="col-md-4"><strong>System:</strong> 🟢 Running</div>
                </div>
            </div>
            """)
            
            # Plugin management section
            html_parts.append("""
            <div class="card">
                <div class="card-header">
                    <h6><i class="fa fa-puzzle-piece"></i> Plugin Management</h6>
                    <small class="text-muted">Enable or disable plugins to control available tools</small>
                </div>
                <div class="card-body">
            """)
            
            # Individual plugin cards
            for plugin in discovered_plugins:
                plugin_name = plugin.get('name', 'Unknown')
                is_enabled = plugin_name in enabled_plugins
                tools_count = len(plugin.get('tools', []))
                
                status_badge = "badge-success" if is_enabled else "badge-secondary"
                status_text = "Enabled" if is_enabled else "Disabled"
                toggle_action = "disable" if is_enabled else "enable"
                toggle_class = "btn-warning" if is_enabled else "btn-success"
                toggle_icon = "fa-pause" if is_enabled else "fa-play"
                
                html_parts.append(f"""
                <div class="plugin-card border rounded p-3 mb-3" style="background: {'#f8f9fa' if is_enabled else '#ffffff'}">
                    <div class="row align-items-center">
                        <div class="col-md-8">
                            <h6 class="mb-1">
                                <i class="fa fa-puzzle-piece text-primary"></i> 
                                {plugin.get('display_name', plugin_name.title())}
                                <span class="badge {status_badge} ml-2">{status_text}</span>
                            </h6>
                            <p class="text-muted mb-1 small">{plugin.get('description', 'No description available')}</p>
                            <small class="text-info">
                                <i class="fa fa-tools"></i> {tools_count} tools • 
                                <i class="fa fa-tag"></i> v{plugin.get('version', '1.0.0')}
                            </small>
                        </div>
                        <div class="col-md-4 text-right">
                            <button type="button" 
                                    class="btn {toggle_class} btn-sm" 
                                    onclick="togglePlugin('{plugin_name}', '{toggle_action}')">
                                <i class="fa {toggle_icon}"></i> {toggle_action.title()}
                            </button>
                        </div>
                    </div>
                </div>
                """)
            
            html_parts.append("""
                </div>
            </div>
            """)
            
            # Tools breakdown by plugin
            if available_tools:
                html_parts.append("""
                <div class="card mt-3">
                    <div class="card-header">
                        <h6><i class="fa fa-list"></i> Tool Distribution</h6>
                    </div>
                    <div class="card-body">
                        <div class="row">
                """)
                
                # Group tools by plugin
                tools_by_plugin = {}
                for tool_name, tool_info in available_tools.items():
                    plugin = tool_info.plugin_name
                    if plugin not in tools_by_plugin:
                        tools_by_plugin[plugin] = []
                    tools_by_plugin[plugin].append(tool_name)
                
                for plugin, plugin_tools in tools_by_plugin.items():
                    html_parts.append(f"""
                    <div class="col-md-6 mb-2">
                        <div class="d-flex justify-content-between align-items-center p-2 border rounded">
                            <span><strong>{plugin.title()}</strong></span>
                            <span class="badge badge-primary">{len(plugin_tools)} tools</span>
                        </div>
                    </div>
                    """)
                
                html_parts.append("""
                        </div>
                    </div>
                </div>
                """)
            
            # Show error plugins (if any)
            error_plugins = [p for p in discovered_plugins if not p.get('can_enable', True)]
            if error_plugins:
                html_parts.append("""
                <div class="alert alert-warning mt-3">
                    <h6><i class="fa fa-exclamation-triangle"></i> Plugin Issues</h6>
                    <ul class="mb-0">
                """)
                for plugin in error_plugins[:3]:
                    error_msg = plugin.get('validation_error', 'Unknown error')
                    html_parts.append(f"<li><strong>{plugin.get('name', 'Unknown')}:</strong> {error_msg}</li>")
                if len(error_plugins) > 3:
                    html_parts.append(f"<li><em>... and {len(error_plugins) - 3} more plugin errors</em></li>")
                html_parts.append("</ul></div>")
            
            # Add JavaScript for plugin toggle
            html_parts.append("""
            <script>
            function togglePlugin(pluginName, action) {
                frappe.call({
                    method: 'toggle_plugin',
                    doc: cur_frm.doc,
                    args: {
                        plugin_name: pluginName,
                        action: action
                    },
                    callback: function(response) {
                        if (!response.exc) {
                            cur_frm.reload_doc();
                            frappe.show_alert({
                                message: __('Plugin {0} {1}d successfully', [pluginName, action]),
                                indicator: 'green'
                            });
                        }
                    }
                });
            }
            </script>
            """)
            
            return {"success": True, "html": "".join(html_parts)}
            
        except Exception as e:
            return {
                "success": False, 
                "html": f"<div class='alert alert-danger'>Error loading plugin status: {str(e)}</div>"
            }
    
    @frappe.whitelist()
    def toggle_plugin(self, plugin_name, action):
        """Enable or disable a plugin"""
        try:
            from frappe_assistant_core.utils.plugin_manager import get_plugin_manager, PluginError
            
            plugin_manager = get_plugin_manager()
            
            if action == "enable":
                result = plugin_manager.enable_plugin(plugin_name)
                message = f"Plugin '{plugin_name}' enabled successfully"
            elif action == "disable":
                result = plugin_manager.disable_plugin(plugin_name)
                message = f"Plugin '{plugin_name}' disabled successfully"
            else:
                frappe.throw(f"Invalid action: {action}")
            
            if result:
                frappe.msgprint(frappe._(message))
                return {"success": True, "message": message}
            else:
                error_msg = f"Failed to {action} plugin '{plugin_name}'"
                frappe.throw(error_msg)
                
        except PluginError as e:
            frappe.log_error(
                title=frappe._("Plugin Toggle Error"),
                message=str(e)
            )
            frappe.throw(frappe._(str(e)))
        except Exception as e:
            frappe.log_error(
                title=frappe._("Plugin Toggle Error"),
                message=str(e)
            )
            frappe.throw(
                frappe._("Failed to {0} plugin '{1}': {2}").format(action, plugin_name, str(e))
            )



def get_context(context):
    context.title = _("assistant Server Settings")
    context.docs = _("Manage the settings for the assistant Server.")
    context.settings = frappe.get_doc("Assistant Core Settings")
#!/usr/bin/env python3
"""
Unified Chat Manager for TMS with Grok Integration
Following xAI documentation best practices for multi-turn conversations, streaming, and function calling
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List, Callable, Type
from datetime import datetime
from pydantic import BaseModel
from openai import OpenAI
from django.db import models
from .models import Ticket

logger = logging.getLogger(__name__)

# Pydantic models for structured data
class SearchTicketsRequest(BaseModel):
    query: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    limit: Optional[int] = 10

class GetTicketDetailsRequest(BaseModel):
    ticket_id: str

class GetTicketAnalyticsRequest(BaseModel):
    days: Optional[int] = 30
    group_by: Optional[str] = "priority"

class CreateTicketRequest(BaseModel):
    subject: str
    body: str
    priority: str = "medium"
    status: str = "open"
    sender: str = "abuse@contabo.com"
    recipient: str = "tangentohost@gmail.com"

class TMSChatManager:
    """
    Unified chat manager for TMS with Grok integration
    Following xAI documentation best practices
    """
    
    def __init__(self, api_key: str, base_url: str = "https://api.x.ai/v1"):
        self.api_key = api_key
        self.grok_client = OpenAI(base_url=base_url, api_key=self.api_key)
        self.messages = []
        self.tools = self._get_tools()
        self.executables = self._get_executables()
        self.arguments = self._get_arguments()
        
        # Initialize with system prompt
        system_prompt = self._get_system_prompt()
        self.messages.append({"role": "system", "content": system_prompt})
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for TMS chat"""
        return """
You are Grok, an expert AI assistant for Tangento's Ticket Management System (TMS), a hosting provider dealing with Contabo abuse complaints.

Your capabilities include:
- Searching and analyzing tickets in the database
- Providing detailed analysis of abuse complaints
- Creating new tickets when needed
- Generating analytics and reports
- Offering professional advice on ticket management

Your role is to:
1. Help users find and analyze tickets
2. Provide context-aware advice based on actual ticket data
3. Assist with ticket management best practices
4. Generate professional response templates
5. Offer compliance and technical guidance

Always maintain a professional, helpful tone. Focus on providing actionable advice based on real ticket data from the database.
"""
    
    def _get_tools(self) -> List[Dict]:
        """Define tools/functions that Grok can call"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_tickets",
                    "description": "Search for tickets in the database based on various criteria",
                    "parameters": SearchTicketsRequest.model_json_schema(),
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_ticket_details",
                    "description": "Get detailed information about a specific ticket including full body content",
                    "parameters": GetTicketDetailsRequest.model_json_schema(),
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_ticket_analytics",
                    "description": "Get analytics and statistics about tickets",
                    "parameters": GetTicketAnalyticsRequest.model_json_schema(),
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_ticket",
                    "description": "Create a new ticket in the database",
                    "parameters": CreateTicketRequest.model_json_schema(),
                }
            }
        ]
    
    def _get_executables(self) -> Dict[str, Callable]:
        """Define executable functions"""
        return {
            "search_tickets": self._search_tickets_tool,
            "get_ticket_details": self._get_ticket_details_tool,
            "get_ticket_analytics": self._get_ticket_analytics_tool,
            "create_ticket": self._create_ticket_tool,
        }
    
    def _get_arguments(self) -> Dict[str, Type[BaseModel]]:
        """Define argument schemas"""
        return {
            "search_tickets": SearchTicketsRequest,
            "get_ticket_details": GetTicketDetailsRequest,
            "get_ticket_analytics": GetTicketAnalyticsRequest,
            "create_ticket": CreateTicketRequest,
        }
    
    def _search_tickets_tool(self, args: SearchTicketsRequest) -> str:
        """Search tickets based on criteria"""
        try:
            tickets = Ticket.objects.all()
            
            # Apply search filters
            if args.query:
                tickets = tickets.filter(
                    models.Q(ticket_id__icontains=args.query) |
                    models.Q(subject__icontains=args.query) |
                    models.Q(body__icontains=args.query)
                )
            
            if args.priority:
                tickets = tickets.filter(priority__iexact=args.priority)
            
            if args.status:
                tickets = tickets.filter(status__iexact=args.status)
            
            # Order by most recent first
            tickets = tickets.order_by('-received_at')[:args.limit]
            
            results = []
            for ticket in tickets:
                results.append({
                    'ticket_id': ticket.ticket_id,
                    'subject': ticket.subject,
                    'body': ticket.body,
                    'priority': ticket.priority,
                    'status': ticket.status,
                    'received_at': ticket.received_at.isoformat() if ticket.received_at else None,
                    'sender': ticket.sender,
                    'recipient': ticket.recipient
                })
            
            return json.dumps({
                "tickets": results,
                "count": len(results),
                "total_found": tickets.count()
            }, indent=2)
            
        except Exception as e:
            logger.error(f"Search tickets error: {e}")
            return json.dumps({"error": f"Search failed: {str(e)}"})
    
    def _get_ticket_details_tool(self, args: GetTicketDetailsRequest) -> str:
        """Get detailed information about a specific ticket"""
        try:
            ticket = Ticket.objects.get(ticket_id=args.ticket_id)
            ticket_data = {
                'ticket_id': ticket.ticket_id,
                'subject': ticket.subject,
                'body': ticket.body,
                'priority': ticket.priority,
                'status': ticket.status,
                'received_at': ticket.received_at.isoformat() if ticket.received_at else None,
                'sender': ticket.sender,
                'recipient': ticket.recipient
            }
            return json.dumps(ticket_data, indent=2)
            
        except Ticket.DoesNotExist:
            return json.dumps({"error": f"Ticket {args.ticket_id} not found"})
        except Exception as e:
            logger.error(f"Get ticket details error: {e}")
            return json.dumps({"error": f"Failed to get ticket details: {str(e)}"})
    
    def _get_ticket_analytics_tool(self, args: GetTicketAnalyticsRequest) -> str:
        """Get analytics about tickets"""
        try:
            from django.db.models import Count
            from datetime import datetime, timedelta
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=args.days)
            
            tickets = Ticket.objects.filter(received_at__range=[start_date, end_date])
            
            if args.group_by == 'priority':
                analytics = tickets.values('priority').annotate(count=Count('priority'))
            elif args.group_by == 'status':
                analytics = tickets.values('status').annotate(count=Count('status'))
            else:
                analytics = tickets.values('priority').annotate(count=Count('priority'))
            
            return json.dumps({
                "analytics": list(analytics),
                "total_tickets": tickets.count(),
                "period_days": args.days,
                "group_by": args.group_by
            }, indent=2)
            
        except Exception as e:
            logger.error(f"Get analytics error: {e}")
            return json.dumps({"error": f"Failed to get analytics: {str(e)}"})
    
    def _create_ticket_tool(self, args: CreateTicketRequest) -> str:
        """Create a new ticket"""
        try:
            from datetime import datetime
            
            ticket = Ticket.objects.create(
                ticket_id=f"TMS{datetime.now().strftime('%Y%m%d%H%M%S')}",
                subject=args.subject,
                body=args.body,
                priority=args.priority,
                status=args.status,
                sender=args.sender,
                recipient=args.recipient,
                received_at=datetime.now()
            )
            
            return json.dumps({
                "success": True,
                "ticket_id": ticket.ticket_id,
                "message": f"Created ticket {ticket.ticket_id}"
            }, indent=2)
            
        except Exception as e:
            logger.error(f"Create ticket error: {e}")
            return json.dumps({"error": f"Failed to create ticket: {str(e)}"})
    
    def _handle_tool_call(self, tool_call: Dict) -> str:
        """Execute a tool call and return the result"""
        try:
            function_name = tool_call["function"]["name"]
            arguments_json = tool_call["function"]["arguments"]
            
            if function_name not in self.executables:
                return json.dumps({"error": f"Unknown function: {function_name}"})
            
            # Parse arguments using Pydantic
            arguments_schema = self.arguments[function_name]
            arguments = arguments_schema.model_validate_json(arguments_json)
            
            # Execute the function
            result = self.executables[function_name](arguments)
            return result
            
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return json.dumps({"error": f"Tool execution failed: {str(e)}"})
    
    def chat(self, user_message: str, stream: bool = False) -> str:
        """
        Main chat method with multi-turn conversation support
        """
        # Add user message to conversation history
        self.messages.append({"role": "user", "content": user_message})
        
        try:
            # Make request to Grok with tools
            response = self.grok_client.chat.completions.create(
                model="grok-4",
                messages=self.messages,
                tools=self.tools,
                stream=stream,
                temperature=0.7,
                max_tokens=3000
            )
            
            if stream:
                return self._handle_streaming_response(response)
            else:
                return self._handle_non_streaming_response(response)
                
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"I apologize, but I encountered an error: {str(e)}"
    
    def _handle_streaming_response(self, response) -> str:
        """Handle streaming response from Grok"""
        model_response = ""
        tool_calls = []
        
        print("Grok: ", end="", flush=True)
        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                model_response += content
                print(content, end="", flush=True)
            
            if chunk.choices[0].delta.tool_calls:
                for tool_call in chunk.choices[0].delta.tool_calls:
                    tool_calls.append(tool_call)
        
        print()  # New line after streaming
        
        # Add assistant message to history
        message = {
            "role": "assistant",
            "content": model_response,
            "tool_calls": [tool_call.model_dump() for tool_call in tool_calls] if tool_calls else None,
        }
        self.messages.append(message)
        
        # Handle tool calls
        if tool_calls:
            for tool_call in tool_calls:
                result = self._handle_tool_call(tool_call.model_dump())
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
            
            # Get final response after tool execution
            final_response = self.grok_client.chat.completions.create(
                model="grok-4",
                messages=self.messages,
                tools=self.tools,
                stream=True,
                temperature=0.7,
                max_tokens=2000
            )
            
            final_content = ""
            print("Grok: ", end="", flush=True)
            for chunk in final_response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    final_content += content
                    print(content, end="", flush=True)
            
            print()  # New line after final response
            self.messages.append({"role": "assistant", "content": final_content})
            return final_content
        
        return model_response
    
    def _handle_non_streaming_response(self, response) -> str:
        """Handle non-streaming response from Grok"""
        choice = response.choices[0]
        message = choice.message
        content = message.content or ""
        tool_calls = message.tool_calls or []
        
        # Add assistant message to history
        assistant_message = {
            "role": "assistant",
            "content": content,
            "tool_calls": [tool_call.model_dump() for tool_call in tool_calls] if tool_calls else None,
        }
        self.messages.append(assistant_message)
        
        # Handle tool calls
        if tool_calls:
            for tool_call in tool_calls:
                result = self._handle_tool_call(tool_call.model_dump())
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
            
            # Get final response after tool execution
            final_response = self.grok_client.chat.completions.create(
                model="grok-4",
                messages=self.messages,
                tools=self.tools,
                temperature=0.7,
                max_tokens=2000
            )
            
            final_content = final_response.choices[0].message.content or ""
            self.messages.append({"role": "assistant", "content": final_content})
            return final_content
        
        return content
    
    def get_conversation_history(self) -> List[Dict]:
        """Get the full conversation history"""
        return self.messages
    
    def reset_conversation(self):
        """Reset the conversation history"""
        self.messages = []
        system_prompt = self._get_system_prompt()
        self.messages.append({"role": "system", "content": system_prompt})
    
    def export_conversation(self) -> str:
        """Export conversation as JSON"""
        return json.dumps(self.messages, indent=2) 
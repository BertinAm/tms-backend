import requests
import json
from decouple import config
from typing import Dict, Any, Optional, List
import logging
import re
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from openai import OpenAI
from django.db import models
from .models import Ticket

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class GrokAPI:
    def __init__(self):
        self.api_key = config('GROK_API_KEY')
        
        # Initialize OpenAI client for Grok
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.x.ai/v1",
        )

    def _make_grok_request(self, messages: list, temperature: float = 0.7, tools: Optional[List] = None) -> Dict[str, Any]:
        """
        Make a request to the Grok API using the official OpenAI client with optional function calling
        """
        try:
            kwargs = {
                "model": "grok-4",
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 3000,  # Increased for longer responses
                "stream": False
            }
            
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            response = self.client.chat.completions.create(**kwargs)
            
            # Convert OpenAI response format to our expected format
            return {
                "choices": [
                    {
                        "message": {
                            "content": response.choices[0].message.content,
                            "tool_calls": getattr(response.choices[0].message, 'tool_calls', None)
                        }
                    }
                ]
            }
                
        except Exception as e:
            logger.error(f"Grok API error: {e}")
            return {"error": f"API request failed: {str(e)}"}

    def _get_database_tools(self) -> List[Dict]:
        """
        Define tools/functions that Grok can call to interact with the database
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_tickets",
                    "description": "Search for tickets in the database based on various criteria",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query to find tickets by ID, subject, or body content"
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "description": "Filter tickets by priority level"
                            },
                            "status": {
                                "type": "string",
                                "enum": ["open", "closed", "pending"],
                                "description": "Filter tickets by status"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of tickets to return (default: 10)"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_ticket_details",
                    "description": "Get detailed information about a specific ticket",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ticket_id": {
                                "type": "string",
                                "description": "The ID of the ticket to retrieve"
                            }
                        },
                        "required": ["ticket_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_ticket_analytics",
                    "description": "Get analytics and statistics about tickets",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "integer",
                                "description": "Number of days to analyze (default: 30)"
                            },
                            "group_by": {
                                "type": "string",
                                "enum": ["priority", "status", "abuse_type"],
                                "description": "How to group the analytics"
                            }
                        },
                        "required": []
                    }
                }
            }
        ]

    def _execute_tool_call(self, tool_call: Dict) -> Dict[str, Any]:
        """
        Execute a tool call and return the result
        """
        function_name = tool_call["function"]["name"]
        arguments = json.loads(tool_call["function"]["arguments"])
        
        try:
            if function_name == "search_tickets":
                return self._search_tickets_tool(arguments)
            elif function_name == "get_ticket_details":
                return self._get_ticket_details_tool(arguments)
            elif function_name == "get_ticket_analytics":
                return self._get_ticket_analytics_tool(arguments)
            else:
                return {"error": f"Unknown function: {function_name}"}
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": f"Tool execution failed: {str(e)}"}

    def _search_tickets_tool(self, args: Dict) -> Dict[str, Any]:
        """
        Search tickets based on criteria
        """
        query = args.get('query', '')
        priority = args.get('priority', '')
        status = args.get('status', '')
        limit = args.get('limit', 10)
        
        tickets = Ticket.objects.all()
        
        # Apply search filters
        if query:
            tickets = tickets.filter(
                models.Q(ticket_id__icontains=query) |
                models.Q(subject__icontains=query) |
                models.Q(body__icontains=query)
            )
        
        if priority:
            tickets = tickets.filter(priority__iexact=priority)
        
        if status:
            tickets = tickets.filter(status__iexact=status)
        
        # Order by most recent first
        tickets = tickets.order_by('-received_at')[:limit]
        
        results = []
        for ticket in tickets:
            results.append({
                'ticket_id': ticket.ticket_id,
                'subject': ticket.subject,
                'body': ticket.body,  # Full body content
                'priority': ticket.priority,
                'status': ticket.status,
                'received_at': ticket.received_at.isoformat() if ticket.received_at else None,
                'sender': ticket.sender,
                'recipient': ticket.recipient
            })
        
        return {
            "tickets": results,
            "count": len(results),
            "total_found": tickets.count()
        }

    def _get_ticket_details_tool(self, args: Dict) -> Dict[str, Any]:
        """
        Get detailed information about a specific ticket
        """
        ticket_id = args.get('ticket_id')
        
        try:
            ticket = Ticket.objects.get(ticket_id=ticket_id)
            return {
                'ticket_id': ticket.ticket_id,
                'subject': ticket.subject,
                'body': ticket.body,  # Full body content
                'priority': ticket.priority,
                'status': ticket.status,
                'received_at': ticket.received_at.isoformat() if ticket.received_at else None,
                'sender': ticket.sender,
                'recipient': ticket.recipient
            }
        except Ticket.DoesNotExist:
            return {"error": f"Ticket {ticket_id} not found"}

    def _get_ticket_analytics_tool(self, args: Dict) -> Dict[str, Any]:
        """
        Get analytics about tickets
        """
        days = args.get('days', 30)
        group_by = args.get('group_by', 'priority')
        
        from django.db.models import Count
        from datetime import datetime, timedelta
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        tickets = Ticket.objects.filter(received_at__range=[start_date, end_date])
        
        if group_by == 'priority':
            analytics = tickets.values('priority').annotate(count=Count('priority'))
        elif group_by == 'status':
            analytics = tickets.values('status').annotate(count=Count('status'))
        else:
            analytics = tickets.values('priority').annotate(count=Count('priority'))
        
        return {
            "analytics": list(analytics),
            "total_tickets": tickets.count(),
            "period_days": days,
            "group_by": group_by
        }

    def _search_tickets_directly(self, search_terms: list, search_filters: dict) -> list:
        """
        Directly search tickets in the database instead of making HTTP requests
        """
        try:
            tickets = Ticket.objects.all()
            
            # Apply search terms
            if search_terms:
                query_conditions = models.Q()
                for term in search_terms:
                    query_conditions |= (
                        models.Q(ticket_id__icontains=term) |
                        models.Q(subject__icontains=term) |
                        models.Q(body__icontains=term)
                    )
                tickets = tickets.filter(query_conditions)
            
            # Apply filters
            if search_filters.get('ticket_ids'):
                tickets = tickets.filter(ticket_id__in=search_filters['ticket_ids'])
            
            if search_filters.get('status'):
                tickets = tickets.filter(status__iexact=search_filters['status'])
            
            if search_filters.get('priority'):
                tickets = tickets.filter(priority__iexact=search_filters['priority'])
            
            if search_filters.get('date'):
                try:
                    date_obj = datetime.strptime(search_filters['date'], '%Y-%m-%d').date()
                    tickets = tickets.filter(received_at__date=date_obj)
                except ValueError:
                    pass
            
            if search_filters.get('abuse_type'):
                abuse_type = search_filters['abuse_type']
                tickets = tickets.filter(
                    models.Q(subject__icontains=abuse_type) |
                    models.Q(body__icontains=abuse_type)
                )
            
            # Order by most recent first
            tickets = tickets.order_by('-received_at')
            
            # Convert to list of dictionaries with full body content
            results = []
            for ticket in tickets[:20]:  # Limit to 20 results
                results.append({
                    'ticket_id': ticket.ticket_id,
                    'subject': ticket.subject,
                    'body': ticket.body,  # Full body content
                    'status': ticket.status,
                    'priority': ticket.priority,
                    'received_at': ticket.received_at.isoformat() if ticket.received_at else None,
                    'sender': ticket.sender,
                    'recipient': ticket.recipient
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Database search error: {e}")
            return []

    def _get_ticket_by_id(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific ticket by ID directly from database
        """
        try:
            ticket = Ticket.objects.get(ticket_id=ticket_id)
            return {
                'ticket_id': ticket.ticket_id,
                'subject': ticket.subject,
                'body': ticket.body,  # Full body content
                'status': ticket.status,
                'priority': ticket.priority,
                'received_at': ticket.received_at.isoformat() if ticket.received_at else None,
                'sender': ticket.sender,
                'recipient': ticket.recipient
            }
        except Ticket.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting ticket {ticket_id}: {e}")
            return None

    def analyze_ticket(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a ticket using Grok AI with full body content
        """
        prompt = self._create_analysis_prompt(ticket_data)
        
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        response = self._make_grok_request(messages, temperature=0.3)
        
        if "error" in response:
            return {
                "error": response["error"],
                "key_issues": [],
                "urgency_level": "unknown",
                "recommended_actions": [],
                "response_template": "Unable to analyze ticket due to API error."
            }
        
        try:
            # Parse the actual Grok API response format
            choices = response.get("choices", [])
            if choices and len(choices) > 0:
                message = choices[0].get("message", {})
                content = message.get("content", "")
                return self._parse_analysis_response(content, ticket_data)
            else:
                logger.error("No choices in Grok response")
                return {
                    "error": "No response from Grok API",
                    "key_issues": [],
                    "urgency_level": "unknown",
                    "recommended_actions": [],
                    "response_template": "Unable to analyze ticket - no response from Grok."
                }
        except Exception as e:
            logger.error(f"Error parsing analysis response: {e}")
            return {
                "error": f"Failed to parse response: {str(e)}",
                "key_issues": [],
                "urgency_level": "unknown",
                "recommended_actions": [],
                "response_template": "Unable to analyze ticket due to parsing error."
            }

    def _create_analysis_prompt(self, ticket_data: Dict[str, Any]) -> str:
        """
        Create a detailed prompt for ticket analysis with full body content
        """
        return f"""
You are an expert cybersecurity and abuse complaint analyst for Tangento's Ticket Management System (TMS). Analyze this Contabo abuse ticket and provide a comprehensive analysis.

TICKET DATA:
- Ticket ID: {ticket_data.get('ticket_id', 'Unknown')}
- Subject: {ticket_data.get('subject', 'No subject')}
- Priority: {ticket_data.get('priority', 'Unknown')}
- Status: {ticket_data.get('status', 'Unknown')}
- Received: {ticket_data.get('received_at', 'Unknown')}
- Sender: {ticket_data.get('sender', 'Unknown')}
- Recipient: {ticket_data.get('recipient', 'Unknown')}

FULL TICKET BODY:
{ticket_data.get('body', 'No body content available')}

Please provide a detailed analysis in the following JSON format:
{{
    "key_issues": ["List of main issues identified from the body content"],
    "urgency_level": "high/medium/low",
    "threat_assessment": "Detailed threat analysis based on body content",
    "recommended_actions": ["List of specific actions to take"],
    "response_template": "Professional response template for the customer",
    "compliance_notes": "Compliance considerations",
    "technical_details": "Technical analysis if applicable",
    "body_analysis": "Analysis of the specific content in the ticket body"
}}

Focus on:
1. Analyzing the full body content for specific abuse details
2. Identifying the type of abuse (spam, copyright, resource abuse, etc.)
3. Assessing urgency and potential impact based on body content
4. Providing specific, actionable recommendations
5. Creating a professional response template
6. Highlighting compliance requirements
7. Technical details if relevant

Be thorough but concise. This is for a hosting provider dealing with Contabo abuse complaints.
"""

    def _parse_analysis_response(self, content: str, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the Grok response and extract structured data
        """
        try:
            # Try to parse as JSON first
            if content.strip().startswith('{'):
                parsed = json.loads(content)
                return {
                    "key_issues": parsed.get("key_issues", []),
                    "urgency_level": parsed.get("urgency_level", "medium"),
                    "threat_assessment": parsed.get("threat_assessment", ""),
                    "recommended_actions": parsed.get("recommended_actions", []),
                    "response_template": parsed.get("response_template", ""),
                    "compliance_notes": parsed.get("compliance_notes", ""),
                    "technical_details": parsed.get("technical_details", ""),
                    "body_analysis": parsed.get("body_analysis", ""),
                    "raw_response": content
                }
            else:
                # If not JSON, extract information from text
                return {
                    "key_issues": ["Analysis provided in text format"],
                    "urgency_level": "medium",
                    "threat_assessment": content[:500] + "..." if len(content) > 500 else content,
                    "recommended_actions": ["Review the detailed analysis above"],
                    "response_template": "Please review the analysis for response guidance.",
                    "compliance_notes": "See threat assessment for compliance details.",
                    "technical_details": "See threat assessment for technical details.",
                    "body_analysis": "See threat assessment for body content analysis.",
                    "raw_response": content
                }
        except json.JSONDecodeError:
            # Fallback to text parsing
            return {
                "key_issues": ["Analysis provided in text format"],
                "urgency_level": "medium",
                "threat_assessment": content[:500] + "..." if len(content) > 500 else content,
                "recommended_actions": ["Review the detailed analysis above"],
                "response_template": "Please review the analysis for response guidance.",
                "compliance_notes": "See threat assessment for compliance details.",
                "technical_details": "See threat assessment for technical details.",
                "body_analysis": "See threat assessment for body content analysis.",
                "raw_response": content
            }

    def chat_with_grok(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Enhanced chat with Grok using function calling and full body content access
        """
        # Enhanced natural language parsing
        message_lower = message.lower()
        
        # Extract ticket IDs (various formats)
        ticket_id_patterns = re.findall(r'(?:ticket\s*#?\s*|#\s*|id\s*|number\s*)([A-Za-z0-9]+)', message_lower)
        
        # Extract other search terms
        search_terms = []
        search_filters = {}
        
        # Extract dates (various formats)
        date_patterns = re.findall(r'(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}|today|yesterday|this week|last week|this month|last month)', message_lower)
        if date_patterns:
            for date_term in date_patterns:
                if date_term == 'today':
                    search_filters['date'] = datetime.now().strftime('%Y-%m-%d')
                elif date_term == 'yesterday':
                    search_filters['date'] = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                elif date_term in ['this week', 'last week', 'this month', 'last month']:
                    search_filters['date_range'] = date_term
                else:
                    search_filters['date'] = date_term
        
        # Extract status terms
        status_keywords = {
            'open': ['open', 'active', 'pending', 'unresolved', 'ongoing'],
            'closed': ['closed', 'resolved', 'completed', 'finished', 'done'],
            'new': ['new', 'recent', 'latest', 'fresh']
        }
        
        for status, keywords in status_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                search_filters['status'] = status
                break
        
        # Extract priority terms
        priority_keywords = {
            'high': ['high priority', 'urgent', 'critical', 'emergency', 'immediate'],
            'medium': ['medium priority', 'moderate', 'normal'],
            'low': ['low priority', 'minor', 'non-urgent']
        }
        
        for priority, keywords in priority_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                search_filters['priority'] = priority
                break
        
        # Extract abuse types
        abuse_keywords = {
            'spam': ['spam', 'email spam', 'bulk email', 'unsolicited'],
            'copyright': ['copyright', 'dmca', 'intellectual property', 'piracy'],
            'ddos': ['ddos', 'attack', 'distributed denial', 'flood'],
            'resource': ['resource abuse', 'cpu abuse', 'bandwidth abuse', 'overuse'],
            'security': ['security breach', 'hack', 'malware', 'virus', 'phishing'],
            'phishing': ['phishing', 'fake', 'scam', 'fraudulent']
        }
        
        for abuse_type, keywords in abuse_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                search_terms.append(abuse_type)
                search_filters['abuse_type'] = abuse_type
                break
        
        # Extract subject keywords
        subject_keywords = re.findall(r'\b(spam|abuse|complaint|issue|problem|violation|suspension|warning|notice|alert|report|incident|breach|attack|malware|virus|phishing|scam|fraud|copyright|dmca|ddos|resource|cpu|bandwidth|email|server|website|domain|hosting|account|user|customer|client)\b', message_lower)
        search_terms.extend(subject_keywords)
        
        # Build enhanced context with function calling
        enhanced_context = context or {}
        
        # If specific ticket ID mentioned, get full details
        if ticket_id_patterns:
            for ticket_id in ticket_id_patterns:
                ticket_data = self._get_ticket_by_id(ticket_id)
                if ticket_data:
                    enhanced_context = ticket_data
                    break
        
        # If no specific ticket found, search for related tickets
        if not enhanced_context.get('ticket_id'):
            found_tickets = self._search_tickets_directly(search_terms, search_filters)
            if found_tickets:
                enhanced_context['found_tickets'] = found_tickets
                enhanced_context['search_query'] = ' '.join(search_terms) if search_terms else 'general search'
        
        # Build context-aware prompt with full body content
        if enhanced_context and enhanced_context.get('ticket_id') and not enhanced_context.get('error'):
            prompt = f"""
You are an expert AI assistant for Tangento's Ticket Management System (TMS), a hosting provider dealing with Contabo abuse complaints.

TICKET DATA:
- Ticket ID: {enhanced_context.get('ticket_id', 'Unknown')}
- Subject: {enhanced_context.get('subject', 'No subject')}
- Priority: {enhanced_context.get('priority', 'Unknown')}
- Status: {enhanced_context.get('status', 'Unknown')}
- Received: {enhanced_context.get('received_at', 'Unknown')}
- Sender: {enhanced_context.get('sender', 'Unknown')}
- Recipient: {enhanced_context.get('recipient', 'Unknown')}

FULL TICKET BODY:
{enhanced_context.get('body', 'No body content available')}

User message: {message}

Please provide helpful, professional advice about this specific ticket. Analyze the full body content and structure your response in clear, well-separated paragraphs:

1. **Ticket Analysis**: Brief overview of the ticket and key issues from the body content
2. **Urgency Assessment**: Priority level and required response time
3. **Recommended Actions**: Specific steps to take based on the body content
4. **Response Template**: Professional response for the customer
5. **Compliance Notes**: Legal or policy considerations
6. **Body Content Analysis**: Specific analysis of the ticket body content

Be concise but thorough. Structure your response in clear, well-separated paragraphs. Avoid markdown formatting and use natural paragraph breaks.
"""
        elif enhanced_context and enhanced_context.get('found_tickets'):
            tickets_info = []
            for ticket in enhanced_context['found_tickets'][:5]:  # Show first 5
                body_preview = ticket['body'][:150] + "..." if len(ticket['body']) > 150 else ticket['body']
                tickets_info.append(f"""
Ticket #{ticket['ticket_id']}:
- Subject: {ticket['subject']}
- Priority: {ticket['priority']}
- Status: {ticket['status']}
- Received: {ticket['received_at']}
- Body Preview: {body_preview}
""")
            
            search_summary = f"Found {len(enhanced_context['found_tickets'])} tickets matching your query"
            if enhanced_context.get('search_query'):
                search_summary += f" (search: {enhanced_context['search_query']})"
            
            prompt = f"""
You are an expert AI assistant for Tangento's Ticket Management System (TMS), a hosting provider dealing with Contabo abuse complaints.

{search_summary}

RELEVANT TICKETS WITH BODY CONTENT:
{chr(10).join(tickets_info)}

User message: {message}

Please provide helpful, professional advice based on these tickets and their body content. Structure your response in clear paragraphs:

1. **Summary**: Overview of the found tickets and key patterns from body content
2. **Analysis**: Common issues and trends identified from ticket bodies
3. **Priority Actions**: Most urgent items requiring attention
4. **Recommendations**: Specific steps and best practices
5. **Response Strategy**: How to handle similar cases based on body content

Be concise but thorough. Structure your response in clear, well-separated paragraphs. Avoid markdown formatting and use natural paragraph breaks.
"""
        else:
            # General query without specific ticket context
            prompt = f"""
You are an expert AI assistant for Tangento's Ticket Management System (TMS), a hosting provider dealing with Contabo abuse complaints.

User message: {message}

Please provide helpful, professional advice about:
- Ticket management best practices
- Abuse complaint handling procedures
- Hosting support guidelines
- Compliance requirements (DMCA, GDPR, etc.)
- Technical troubleshooting
- Response templates and recommendations

Structure your response in clear, well-organized paragraphs. Be concise but thorough. Avoid markdown formatting.
"""

        # Use function calling for enhanced database access
        tools = self._get_database_tools()
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        response = self._make_grok_request(messages, temperature=0.7, tools=tools)
        
        if "error" in response:
            return f"I apologize, but I'm unable to process your request at the moment due to an API error: {response['error']}"
        
        try:
            choices = response.get("choices", [])
            if choices and len(choices) > 0:
                message_obj = choices[0].get("message", {})
                content = message_obj.get("content", "")
                tool_calls = message_obj.get("tool_calls")
                
                # Handle tool calls if present
                if tool_calls:
                    tool_results = []
                    for tool_call in tool_calls:
                        result = self._execute_tool_call(tool_call)
                        tool_results.append(result)
                    
                    # Add tool results to context and get final response
                    if tool_results:
                        enhanced_prompt = f"""
Based on the database query results, please provide a comprehensive analysis:

{json.dumps(tool_results, indent=2)}

Original user message: {message}

Please provide a detailed response based on the actual ticket data from the database.
"""
                        
                        final_response = self._make_grok_request([
                            {"role": "user", "content": enhanced_prompt}
                        ], temperature=0.7)
                        
                        if "error" not in final_response:
                            final_choices = final_response.get("choices", [])
                            if final_choices and len(final_choices) > 0:
                                final_content = final_choices[0].get("message", {}).get("content", "")
                                cleaned_content = self._clean_response(final_content)
                                return cleaned_content if cleaned_content else "I apologize, but I couldn't generate a response. Please try again."
                
                # If no tool calls, return the direct response
                cleaned_content = self._clean_response(content)
                return cleaned_content if cleaned_content else "I apologize, but I couldn't generate a response. Please try again."
            else:
                return "I apologize, but I couldn't generate a response. Please try again."
        except Exception as e:
            logger.error(f"Error processing Grok response: {e}")
            return f"I apologize, but there was an error processing the response: {str(e)}"

    def _clean_response(self, content: str) -> str:
        """
        Clean Grok response and format it into well-structured paragraphs
        """
        # Remove markdown formatting
        cleaned = re.sub(r'[#*`\-_]+', '', content).strip()
        
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', cleaned)
        
        # Group sentences into paragraphs (3-4 sentences per paragraph)
        paragraphs = []
        current_paragraph = []
        
        for sentence in sentences:
            if sentence.strip():
                current_paragraph.append(sentence.strip())
                
                # Start new paragraph after 3-4 sentences or if sentence is very long
                if len(current_paragraph) >= 4 or len(sentence) > 200:
                    if current_paragraph:
                        paragraphs.append(' '.join(current_paragraph))
                        current_paragraph = []
        
        # Add remaining sentences
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))
        
        # If response is short, return as is
        if len(paragraphs) <= 1:
            return cleaned
        
        # Format with double line breaks between paragraphs
        formatted_response = '\n\n'.join(paragraphs)
        
        # Clean up any extra whitespace and remove unwanted separators
        formatted_response = re.sub(r'─{20,}', '', formatted_response)
        formatted_response = re.sub(r'\n{3,}', '\n\n', formatted_response)
        formatted_response = formatted_response.strip()
        
        return formatted_response

    def _simulate_grok_analysis(self, ticket_data: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        """
        Fallback simulation if real API fails
        """
        subject = ticket_data.get('subject', '').lower()
        body = ticket_data.get('body', '').lower()
        
        # Simple keyword-based analysis
        if 'spam' in subject or 'spam' in body:
            return {
                "key_issues": ["Spam activity detected", "Email abuse"],
                "urgency_level": "high",
                "threat_assessment": "Spam activity detected on server. Immediate action required.",
                "recommended_actions": ["Suspend account", "Investigate email logs", "Contact customer"],
                "response_template": "We have received a spam complaint. Please investigate immediately.",
                "compliance_notes": "Spam violates hosting terms of service.",
                "technical_details": "Check email logs and spam filters.",
                "body_analysis": f"Body content analysis: {body[:200]}..."
            }
        elif 'copyright' in subject or 'dmca' in subject:
            return {
                "key_issues": ["Copyright violation", "DMCA complaint"],
                "urgency_level": "high",
                "threat_assessment": "Copyright violation reported. Legal action possible.",
                "recommended_actions": ["Remove infringing content", "Contact customer", "Document actions"],
                "response_template": "Copyright violation reported. Please remove content immediately.",
                "compliance_notes": "DMCA compliance required.",
                "technical_details": "Check for infringing files and remove them.",
                "body_analysis": f"Body content analysis: {body[:200]}..."
            }
        else:
            return {
                "key_issues": ["General abuse complaint"],
                "urgency_level": "medium",
                "threat_assessment": "Abuse complaint received. Investigation needed.",
                "recommended_actions": ["Investigate complaint", "Contact customer", "Monitor activity"],
                "response_template": "We have received an abuse complaint. Please investigate.",
                "compliance_notes": "Review hosting terms of service.",
                "technical_details": "Check server logs and user activity.",
                "body_analysis": f"Body content analysis: {body[:200]}..."
            }

    def _simulate_grok_chat(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Fallback simulation for chat responses
        """
        message_lower = message.lower()
        
        if 'ticket' in message_lower:
            return "I can help you with ticket management. What specific information do you need about the tickets?"
        elif 'abuse' in message_lower:
            return "For abuse complaints, we recommend immediate investigation and customer contact. What type of abuse are you dealing with?"
        elif 'priority' in message_lower:
            return "Ticket priority is determined by the type and severity of the abuse complaint. High priority tickets require immediate attention."
        else:
            return "I'm here to help with your hosting and abuse complaint management. How can I assist you today?" 
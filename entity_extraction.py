import json
import re
import os
import openai
from typing import Dict, Any, List, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class EntityExtractor:
    """Extract entities from text using OpenAI API."""

    def __init__(self):
        """Initialize the entity extractor."""
        print(f"Setting up entity extraction with OpenAI")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("WARNING: OPENAI_API_KEY not found in environment variables")
        openai.api_key = api_key

    def extract_entities(self, text: str) -> Dict[str, Any]:
        """
        Extract event planning entities from text using OpenAI API.
        Returns a dictionary of entity types and their values.
        """
        if not text or text.strip() == "":
            return {}

        try:
            # First try with OpenAI for better entity extraction
            openai_entities = self._extract_entities_with_openai(text)
            
            # As a fallback, supplement with regex patterns for specific event planning entity types
            regex_entities = self._extract_entities_with_regex(text)
            
            # Merge both extraction methods, preferring OpenAI results
            entities = {**regex_entities, **openai_entities}
            
            return entities

        except Exception as e:
            print(f"Error in entity extraction with OpenAI: {str(e)}")
            # Fall back to simple extraction if there's any error
            return self._extract_entities_with_regex(text)
    
    def _extract_entities_with_openai(self, text: str) -> Dict[str, Any]:
        """Extract entities using OpenAI."""
        system_prompt = """
        You are an expert entity extraction system. Extract entities from the input text related to event planning.
        Return a JSON object with the following structure (only include fields if they are present in the text):
        {
            "people": [list of people mentioned],
            "organizations": [list of organizations],
            "location": "the event location",
            "date": "the event date",
            "time": "the event time",
            "budget": "the event budget",
            "cost": "the event cost per person or ticket",
            "event_type": "type of event (meeting, party, etc.)",
            "theme": "event theme if mentioned",
            "attendees": "number of attendees",
            "contacts": {
                "email": "contact email if present",
                "phone": "contact phone if present"
            }
        }
        
        IMPORTANT: Only extract information that is explicitly mentioned in the text. Do not make assumptions.
        IMPORTANT: Return valid JSON only, no additional text.
        IMPORTANT: If a list field has only one item, still format it as a list.
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.1  # Lower temperature for more deterministic outputs
            )
            
            # Extract the response content
            response_text = response.choices[0].message.content
            
            # Parse the JSON response
            entities = json.loads(response_text)
            
            # Ensure we have a consistent format
            if "contacts" in entities:
                if "email" in entities["contacts"] and entities["contacts"]["email"]:
                    entities["email"] = entities["contacts"]["email"]
                if "phone" in entities["contacts"] and entities["contacts"]["phone"]:
                    entities["phone"] = entities["contacts"]["phone"]
                del entities["contacts"]
                
            return entities
            
        except Exception as e:
            print(f"Error in OpenAI entity extraction: {str(e)}")
            return {}
    
    def _extract_entities_with_regex(self, text: str) -> Dict[str, Any]:
        """Extract entities using regex patterns."""
        entities = {}
        
        # Simple date extraction
        date_patterns = [
            r'(?i)(?:on|for|at|by)\s+([A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?)',  # on January 1st
            r'(?i)(?:on|for|at|by)\s+(\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+)',  # on 1st January
            r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b',  # MM/DD/YYYY or DD/MM/YYYY
            r'\b(\d{1,2}-\d{1,2}-\d{2,4})\b',  # MM-DD-YYYY or DD-MM-YYYY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                entities["date"] = match.group(1)
                break
                
        # Basic time extraction
        time_patterns = [
            r'\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)\b',  # 3:30 PM
            r'\b(\d{1,2}\s*(?:AM|PM|am|pm))\b',  # 3 PM
            r'(?i)(from\s+\d{1,2}(?::\d{2})?\s*(?:AM|PM)?\s*to\s+\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)',  # from 3 PM to 5 PM
            r'(?i)(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?\s*[-–—]\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)',  # 3 PM - 5 PM
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, text)
            if match:
                entities["time"] = match.group(1)
                break
                
        # Basic location extraction
        location_patterns = [
            r'(?i)(?:at|in|location[:]?)\s+([A-Za-z\s]+(?:Center|Hall|Room|Building|Park|Plaza|Hotel|House|Garden|Theater|Theatre|Stadium|Arena))',
            r'(?i)((?:in|at)\s+the\s+[A-Za-z\s]+)',  # at the Place
            r'(?i)(?:venue|location|place)[:\s]+([A-Za-z0-9\s]+)'  # venue: Place Name
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match:
                entities["location"] = match.group(1).strip()
                break
        
        # Budget/cost extraction
        money_patterns = [
            r'(?i)(?:budget|cost|price)[:\s]+(\$\d+(?:,\d+)?(?:\.\d+)?)',  # budget: $1000
            r'(?i)(?:budget|cost|price)[:\s]+(\d+(?:,\d+)?(?:\.\d+)?\s*(?:dollars|USD))',  # budget: 1000 dollars
        ]
        
        for pattern in money_patterns:
            match = re.search(pattern, text)
            if match:
                if "budget" in text.lower():
                    entities["budget"] = match.group(1)
                else:
                    entities["cost"] = match.group(1)
                break
        
        # Contact extraction
        email_pattern = r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b'
        email_match = re.search(email_pattern, text)
        if email_match:
            entities["email"] = email_match.group(1)
            
        phone_pattern = r'\b(\+?1?\s*\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})\b'
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            entities["phone"] = phone_match.group(1)
        
        # Extract event types
        event_types = ["birthday", "wedding", "conference", "meeting", "party", "celebration", 
                       "ceremony", "reception", "dinner", "lunch", "breakfast", "brunch", 
                       "festival", "concert", "seminar", "workshop", "gala"]
        
        for event_type in event_types:
            if event_type.lower() in text.lower():
                entities["event_type"] = event_type
                break
                
        # Extract themes
        themes = ["star wars", "halloween", "christmas", "superhero", "disney", "harry potter", 
                 "beach", "garden", "formal", "casual", "black tie", "masquerade"]
        
        for theme in themes:
            if theme.lower() in text.lower():
                entities["theme"] = theme
                break

        # Extract number of people/attendees
        attendees_patterns = [
            r'(?i)(?:for|with)\s+(\d+)\s+(?:people|attendees|guests|participants)',
            r'(?i)(?:people|attendees|guests|participants)[:\s]+(\d+)',
        ]
        
        for pattern in attendees_patterns:
            match = re.search(pattern, text)
            if match:
                entities["attendees"] = match.group(1)
                break
        
        return entities
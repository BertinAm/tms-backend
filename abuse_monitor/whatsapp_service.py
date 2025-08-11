import logging
import threading
import time
import os
from datetime import datetime, timedelta
from typing import Optional
from decouple import config
from dotenv import load_dotenv
import pywhatkit

# Load environment variables
load_dotenv()

# Set environment variables for headless operation
os.environ['DISPLAY'] = ':0'
os.environ['PYTHONUNBUFFERED'] = '1'

logger = logging.getLogger(__name__)

class WhatsAppService:
    """
    WhatsApp service using pywhatkit for sending messages
    """
    
    def __init__(self):
        self.phone_number = config('CEO_PHONE_NUMBER', default='+237671836872')
        self.is_initialized = False
        
    def initialize(self):
        """
        Initialize WhatsApp Web connection
        """
        try:
            # pywhatkit auto-detects Chrome driver in newer versions
            # No need to manually set driver path
            self.is_initialized = True
            logger.info("WhatsApp service initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize WhatsApp service: {e}")
            return False
    
    def send_whatsapp_message(self, message: str) -> bool:
        """
        Send WhatsApp message with proper timing
        """
        if not self.is_initialized:
            if not self.initialize():
                return False
        
        try:
            # Calculate time 3 minutes from now to ensure enough wait time
            now = datetime.now()
            send_time = now + timedelta(minutes=3)
            
            # Send message in background thread to avoid blocking
            def send_message():
                try:
                    pywhatkit.sendwhatmsg(
                        self.phone_number,
                        message,
                        send_time.hour,
                        send_time.minute,
                        wait_time=120,  # Wait 2 minutes for WhatsApp Web to load
                        tab_close=True,
                        close_time=5
                    )
                    logger.info(f"WhatsApp message sent successfully to {self.phone_number}")
                except Exception as e:
                    logger.error(f"Error sending WhatsApp message: {e}")
                    # Try alternative method if first fails
                    try:
                        pywhatkit.sendwhatmsg_instantly(
                            self.phone_number,
                            message,
                            wait_time=120,
                            tab_close=True,
                            close_time=5
                        )
                        logger.info(f"WhatsApp message sent successfully using instant method")
                    except Exception as e2:
                        logger.error(f"Alternative WhatsApp sending also failed: {e2}")
            
            # Start sending in background thread
            thread = threading.Thread(target=send_message, daemon=True)
            thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Error in send_whatsapp_message: {e}")
            return False
    
    def send_whatsapp_message_instant(self, message: str) -> bool:
        """
        Send WhatsApp message instantly without scheduling
        """
        if not self.is_initialized:
            if not self.initialize():
                return False
        
        try:
            # Send message in background thread to avoid blocking
            def send_message():
                try:
                    pywhatkit.sendwhatmsg_instantly(
                        self.phone_number,
                        message,
                        wait_time=120,  # Wait 2 minutes for WhatsApp Web to load
                        tab_close=True,
                        close_time=5
                    )
                    logger.info(f"WhatsApp message sent successfully to {self.phone_number}")
                except Exception as e:
                    logger.error(f"Error sending instant WhatsApp message: {e}")
            
            # Start sending in background thread
            thread = threading.Thread(target=send_message, daemon=True)
            thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Error in send_whatsapp_message_instant: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        Test WhatsApp connection
        """
        try:
            test_message = f"TMS Email Monitor Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            return self.send_whatsapp_message_instant(test_message)
        except Exception as e:
            logger.error(f"WhatsApp connection test failed: {e}")
            return False 
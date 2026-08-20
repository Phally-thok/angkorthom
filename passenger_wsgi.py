import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Import Flask app as WSGI application
from app import app as application

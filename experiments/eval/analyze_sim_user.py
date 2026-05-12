import asyncio
import logging
import pandas as pd
from typing import Dict, Any, Optional, Union
import argparse
import os
from datetime import datetime

from autogen_core.models import (
    ChatCompletionClient,
    UserMessage,
    SystemMessage,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
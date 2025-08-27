#!/usr/bin/env python3
"""
Test script to isolate browser initialization issues
"""
import asyncio
import sys
import traceback
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from magentic_ui.tools.playwright.browser.local_playwright_browser import LocalPlaywrightBrowser

async def test_local_browser():
    """Test LocalPlaywrightBrowser initialization"""
    print("Testing LocalPlaywrightBrowser initialization...")
    
    # Test with headless=True (current configuration)
    print("\n1. Testing with headless=True...")
    browser_headless = LocalPlaywrightBrowser(headless=True)
    
    try:
        print("   Starting browser...")
        async with browser_headless as browser:
            print("   ✓ Browser started successfully!")
            
            print("   Getting browser context...")
            context = browser.browser_context
            print("   ✓ Browser context obtained!")
            
            print("   Creating a new page...")
            page = await context.new_page()
            print("   ✓ Page created!")
            
            print("   Navigating to google.com...")
            await page.goto("https://www.google.com", timeout=10000)
            print("   ✓ Navigation successful!")
            
        print("   ✓ Browser closed successfully!")
        
    except Exception as e:
        print(f"   ✗ Error with headless=True: {e}")
        traceback.print_exc()
    
    # Test with headless=False 
    print("\n2. Testing with headless=False...")
    browser_headful = LocalPlaywrightBrowser(headless=False)
    
    try:
        print("   Starting browser...")
        async with browser_headful as browser:
            print("   ✓ Browser started successfully!")
            
            print("   Getting browser context...")
            context = browser.browser_context
            print("   ✓ Browser context obtained!")
            
            print("   Creating a new page...")
            page = await context.new_page()
            print("   ✓ Page created!")
            
            print("   Navigating to google.com...")
            await page.goto("https://www.google.com", timeout=10000)
            print("   ✓ Navigation successful!")
            
        print("   ✓ Browser closed successfully!")
        
    except Exception as e:
        print(f"   ✗ Error with headless=False: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    print("Starting browser initialization test...")
    print("Environment: WSL2")
    print("="*50)
    
    asyncio.run(test_local_browser())
    print("\nTest completed!")

#!/usr/bin/env python3
"""
Test script to verify if the new API provider supports the original send_prompt_n
implementation using OpenAI's native 'n' parameter for multiple responses.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from openai import OpenAI
from src.env import openai_api_key, openai_base_url, default_model, global_seed
import termcolor

def test_original_send_prompt_n():
    """Test the original send_prompt_n implementation with native 'n' parameter"""
    
    print(termcolor.colored("=== Testing original send_prompt_n with native 'n' parameter ===", "cyan"))
    print(termcolor.colored(f"API Base URL: {openai_base_url}", "cyan"))
    print(termcolor.colored(f"Model: {default_model}", "cyan"))
    
    # Test parameters
    role_prompt = "You are a helpful assistant."
    user_prompt = "Please generate a simple Python function that adds two numbers. Return only the code."
    n = 3
    
    try:
        client = OpenAI(
            base_url=openai_base_url,
            api_key=openai_api_key
        )
        
        messages = []
        if role_prompt != "":
            messages.append({
                "role": "system",
                "content": role_prompt,
            })

        messages.append({
            "role": "user", 
            "content": user_prompt,  
        })
        
        print(termcolor.colored(f"Sending prompt with n={n} parameter...", "yellow"))
        
        completion = client.chat.completions.create(
            model=default_model,
            temperature=0.9,
            messages=messages,
            max_tokens=1000,
            n=n,  # This is the key parameter from original implementation
            seed=global_seed,
        )
        
        print(termcolor.colored("Received response successfully!", "green"))
        
        # Extract multiple responses
        msglist = [completion.choices[i].message.content for i in range(n)]
        
        print(termcolor.colored(f"\nReceived {len(msglist)} responses:", "green"))
        
        for i, response in enumerate(msglist):
            print(termcolor.colored(f"\n--- Response {i+1} ---", "blue"))
            print(response)
        
        # Check if we got the expected number of responses
        if len(msglist) == n:
            print(termcolor.colored(f"\n✅ SUCCESS: API provider supports native 'n' parameter!", "green"))
            return True
        else:
            print(termcolor.colored(f"\n⚠️  WARNING: Expected {n} responses, got {len(msglist)}", "yellow"))
            return len(msglist) > 0
            
    except Exception as e:
        print(termcolor.colored(f"\n❌ ERROR: Failed to test native 'n' parameter: {e}", "red"))
        return False

def test_current_implementation():
    """Test current implementation that uses multiple API calls"""
    
    print(termcolor.colored("\n=== Testing current implementation (multiple API calls) ===", "cyan"))
    
    from src.llm.utils.llm_util import send_prompt_n
    
    role_prompt = "You are a helpful assistant."
    user_prompt = "Please generate a simple Python function that multiplies two numbers. Return only the code."
    
    try:
        responses = send_prompt_n(
            role_prompt=role_prompt,
            user_prompt=user_prompt,
            n=3,
            model=default_model,
            temperature=0.8,
            test_speed=False
        )
        
        if responses and len(responses) == 3:
            print(termcolor.colored("✅ Current implementation works correctly", "green"))
            return True
        else:
            print(termcolor.colored(f"⚠️  Current implementation returned {len(responses) if responses else 0} responses", "yellow"))
            return False
            
    except Exception as e:
        print(termcolor.colored(f"❌ ERROR: Current implementation failed: {e}", "red"))
        return False

if __name__ == "__main__":
    print("Testing new API provider support for original send_prompt_n implementation...")
    
    # Test current implementation first
    current_success = test_current_implementation()
    
    # Test original implementation
    original_success = test_original_send_prompt_n()
    
    print(termcolor.colored("\n=== TEST RESULTS ===", "cyan"))
    print(termcolor.colored(f"Current implementation (multiple calls): {'PASS' if current_success else 'FAIL'}", "green" if current_success else "red"))
    print(termcolor.colored(f"Original implementation (native 'n' parameter): {'PASS' if original_success else 'FAIL'}", "green" if original_success else "red"))
    
    if original_success:
        print(termcolor.colored("\n🎉 The new API provider supports the original implementation! You can revert to the simpler code.", "green"))
        sys.exit(0)
    elif current_success:
        print(termcolor.colored("\n⚠️  Only current implementation works. The API provider doesn't support native 'n' parameter.", "yellow"))
        sys.exit(1)
    else:
        print(termcolor.colored("\n❌ Both implementations failed. The API provider may not be compatible.", "red"))
        sys.exit(2)
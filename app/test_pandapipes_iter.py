#!/usr/bin/env python3
"""Test script to understand pandapipes iteration behavior."""
import inspect
try:
    import pandapipes as pp
    print(f"pandapipes version: {pp.__version__ if hasattr(pp, '__version__') else 'unknown'}")
    
    # Check pipeflow signature
    sig = inspect.signature(pp.pipeflow)
    print(f"\npandapipes.pipeflow parameters:")
    for param_name, param in sig.parameters.items():
        default = param.default if param.default != inspect.Parameter.empty else "REQUIRED"
        print(f"  {param_name}: {default}")
    
    # Check if there's run_control or options
    net = pp.create_empty_network(fluid="water")
    print(f"\nNetwork attributes:")
    for attr in dir(net):
        if not attr.startswith('_') and 'control' in attr.lower() or 'option' in attr.lower() or 'iter' in attr.lower():
            print(f"  {attr}: {getattr(net, attr, 'N/A')}")
    
except ImportError:
    print("pandapipes not installed")
